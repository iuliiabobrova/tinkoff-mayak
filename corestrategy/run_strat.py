import asyncio
from typing import List
from time import perf_counter

from threading import Event
from queue import Queue
from pandas import DataFrame, concat
from tinkoff.invest import CandleInterval

from corestrategy.hitoric_data_calc import (
    recalc_sma_if_inactual,
    calc_std_deviation,
    calc_historic_signals_sma
)
from corestrategy.utils import (
    is_time_to_download_data,
    market_is_closed,
    wait_until_download_time,
    wait_until_market_is_open,
    now_msk
)
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.historic_data_download import (
    download_shares,
    get_figi_list_with_inactual_historic_data,
    download_historic_candles
)
from corestrategy.strategy_sma import calc_actual_signals_sma
from corestrategy.strategy_rsi import calc_actual_signals_rsi
from corestrategy.delivery_boy import run_delivery_boy
from tgbot.models import HistoricCandle, Share, Strategy


def calc_strategies(
        df_previous_sma_list: DataFrame,
        queue: Queue,
        n: int
) -> List:
    start_time = perf_counter()
    df_all_lasts = get_all_lasts()
    df_actual_signals = DataFrame(columns=columns_rsi)

    [df_historic_signals_sma_50_200,
     df_previous_sma_50_200,
     df_actual_sgnls_sma_50_200] = calc_actual_signals_sma(
        n=n,
        df_all_lasts=df_all_lasts,
        df_previous_sma=df_previous_sma_list[0],
        sma_periods=sma_cross_periods_50_200,
        df_actual_signals=df_actual_signals
    )
    [df_historic_signals_sma_30_90,
     df_previous_sma_30_90,
     df_actual_sgnls_sma_30_90] = calc_actual_signals_sma(
        n=n,
        df_all_lasts=df_all_lasts,
        df_previous_sma=df_previous_sma_list[1],
        sma_periods=sma_cross_periods_30_90,
        df_actual_signals=df_actual_signals
    )
    [df_historic_signals_sma_20_60,
     df_previous_sma_20_60,
     df_actual_sgnls_sma_20_60] = calc_actual_signals_sma(
        n=n,
        df_all_lasts=df_all_lasts,
        df_previous_sma=df_previous_sma_list[2],
        sma_periods=sma_cross_periods_20_60,
        df_actual_signals=df_actual_signals
    )
    df_historic_signals_sma_list = [
        df_historic_signals_sma_50_200,
        df_historic_signals_sma_30_90,
        df_historic_signals_sma_20_60
    ]
    df_previous_sma_list = [
        df_previous_sma_50_200,
        df_previous_sma_30_90,
        df_previous_sma_20_60
    ]

    [df_historic_signals_rsi, df_actual_sgnls_rsi] = calc_actual_signals_rsi(
        df_all_lasts=df_all_lasts,
        df_actual_signals=df_actual_signals
    )

    df_actual_sgnls = concat(objs=[df_actual_sgnls_rsi,
                                   df_actual_sgnls_sma_20_60,
                                   df_actual_sgnls_sma_50_200,
                                   df_actual_sgnls_sma_30_90])

    queue = run_delivery_boy(df_actual_sgnls, queue)
    del df_actual_sgnls

    n += 1
    run_time = perf_counter() - start_time
    if run_time < 60:
        Event().wait(timeout=60 - run_time)

    return [df_previous_sma_list, n, queue]


async def update_data():
    """Функция обновляет все исторические данные: Share, HistoricCandle, MovingAverage, RSI, Signal"""
    print('⏩START DATA CHECK. It can take 2 hours')

    download_shares()
    figi_list = get_figi_list_with_inactual_historic_data(HistoricCandle)[:3]
    asyncio.run(download_historic_candles(figi_list=figi_list))
    await recalc_sma_if_inactual()
    for periods in Strategy.SMACrossPeriods.all():
        calc_historic_signals_sma(periods=periods, figi_list=figi_list, interval=CandleInterval.CANDLE_INTERVAL_DAY)

    shares = Share.objects.filter(figi__in=figi_list)

    # # проверка rsi-signals на актуальность
    # if exists(path='csv/historic_signals_rsi.csv'):
    #     df = read_csv(
    #         filepath_or_buffer='csv/historic_signals_rsi.csv',
    #         sep=';',
    #         index_col=0,
    #         parse_dates=['datetime'],
    #         low_memory=False
    #     )
    #     if historic_data_is_actual(df=df):
    #         df_historic_signals_rsi = df
    #         df_rsi = read_csv(
    #             filepath_or_buffer='csv/rsi.csv',
    #             sep=';',
    #             index_col=0
    #         )
    #     else:
    #         save_historic_signals_rsi()
    # else:
    #     save_historic_signals_rsi()

    calc_std_deviation(figi_list=figi_list)
    # calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)  TODO RSI-profit
    print('✅All data is actual')


def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    n = 0
    queue1 = Queue()

    asyncio.create_task(update_data())  # TODO check async

    # Пустые DataFrame
    df_previous_sma_50_200 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_30_90 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_20_60 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_list = [df_previous_sma_50_200, df_previous_sma_30_90, df_previous_sma_20_60]

    while True:
        if market_is_closed() and not is_time_to_download_data():
            print(f'Market is closed now. Now-time: {now_msk()}')
            wait_until_download_time()
        elif is_time_to_download_data():
            print(f'Time to download data. Now-time: {now_msk()}')
            update_data()
            wait_until_market_is_open()
        while not market_is_closed():
            [
                df_previous_sma_list,
                queue1,
                n
            ] = calc_strategies(
                df_previous_sma_list=df_previous_sma_list,
                queue=queue1,
                n=n
            )
