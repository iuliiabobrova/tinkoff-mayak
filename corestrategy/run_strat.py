import asyncio
from typing import List
from time import perf_counter

from queue import Queue
from pandas import DataFrame, concat
from tinkoff.invest import CandleInterval

from corestrategy.hitoric_data_calc import (
    recalc_sma_if_inactual,
    calc_std_deviation,
    calc_rsi_float,
    calc_historic_signals_rsi,
    SMASignalsCalculator
)
from corestrategy.utils import (
    is_time_to_download_data,
    market_is_closed,
    wait_until_download_time,
    wait_until_market_is_open,
    now_msk, Limit
)
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.historic_data_download import (
    download_shares,
    get_figi_with_inactual_historic_data,
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
        asyncio.sleep(delay=60 - run_time)

    return [df_previous_sma_list, n, queue]


async def update_data(figi: str):
    """Функция обновляет все исторические данные: Share, HistoricCandle, MovingAverage, RSI, Signal"""

    await download_historic_candles(figi_tuple=figi)
    await recalc_sma_if_inactual(figi_tuple=figi)

    for periods in Strategy.SMACross.Periods.all():
        calculator = SMASignalsCalculator(
            figi=figi,
            periods=periods
        )
        await calculator.calc_historic_signals()
        # calc_rsi_float()
        # calc_historic_signals_rsi()

    #calc_std_deviation(figi_list=figi_list)
    # calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)  TODO RSI-profit


async def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    @Limit(calls=3, period=60)  # API позволяет запрашивать свечи не более 300 раз в минуту
    async def create_update_data_task():
        return asyncio.create_task(update_data(figi=figi))

    n = 0
    queue1 = Queue()

    await download_shares()
    figi_tuple = await get_figi_with_inactual_historic_data(HistoricCandle)
    tasks = []
    for figi in figi_tuple:
        tasks += [await create_update_data_task()]
    for task in tasks:
        await task

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
            await update_data()
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
