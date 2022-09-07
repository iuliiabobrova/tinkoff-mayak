import asyncio
from typing import List, NoReturn
from time import perf_counter

from queue import Queue
from pandas import DataFrame, concat
from tinkoff.invest import CandleInterval

from corestrategy.hitoric_data_calc import (
    SMASignalsCalculator,
    RSISignalsCalculator
)
from corestrategy.utils import (
    is_time_to_download_data,
    market_is_closed,
    wait_until_download_time,
    wait_until_market_is_open,
    now_msk, Limit, closeprices_dataframe_for_figi
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
from tgbot.models import HistoricCandle, Share, Strategy, StrategyRSI


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

    await download_historic_candles(figi=figi)
    df_historic_close_prices = await closeprices_dataframe_for_figi(figi=figi)
    print(df_historic_close_prices)

    for strategy in Strategy.SMACross.all():
        ma_calculator = SMASignalsCalculator(
            figi=figi,
            strategy=strategy
        )
        await ma_calculator.calc_indicator(df_historic_close_prices=df_historic_close_prices)
        await ma_calculator.calc_historic_signals()
    for strategy in StrategyRSI.all():
        rsi_calculator = RSISignalsCalculator(
            figi=figi,
            strategy=strategy
        )
        df_rsi = await rsi_calculator.calc_indicator(df_historic_close_prices=df_historic_close_prices)
        await rsi_calculator.calc_one_figi_signals_rsi(df_historic_close_prices=df_historic_close_prices, df_rsi=df_rsi)


async def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    n = 0
    queue1 = Queue()  # TODO - это очередь на отправку сигналов. Если решим не использовать threading и объект Queue, нужна новая логика

    async def update_data_task() -> NoReturn:

        @Limit(calls=2, period=60)  # API позволяет запрашивать свечи не более 300 раз в минуту TODO выставить корректные лимиты, 2 в минуту тестово
        async def create_update_data_task():
            return asyncio.create_task(update_data(figi=figi))

        await download_shares()
        figi_tuple = await get_figi_with_inactual_historic_data(HistoricCandle)
        tasks = []
        for figi in figi_tuple:
            tasks += [await create_update_data_task()]
        for task in tasks:
            await task

    # Пустые DataFrame TODO can we delete it?
    df_previous_sma_50_200 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_30_90 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_20_60 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_list = [df_previous_sma_50_200, df_previous_sma_30_90, df_previous_sma_20_60]

    await update_data_task()
    while True:
        if market_is_closed() and not is_time_to_download_data():
            print(f'Market is closed now. Now-time: {now_msk()}')
            wait_until_download_time()
        elif is_time_to_download_data():
            print(f'Time to download data. Now-time: {now_msk()}')
            await update_data_task()
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
