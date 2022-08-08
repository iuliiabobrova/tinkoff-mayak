from typing import List
from time import perf_counter

from threading import Event
from queue import Queue
from pandas import DataFrame, concat

from corestrategy.settings import sma_cross_periods_50_200, sma_cross_periods_30_90, \
    sma_cross_periods_20_60
from corestrategy.utils import (is_time_to_download_data,
                                market_is_closed,
                                wait_until_download_time,
                                wait_until_market_is_open,
                                _msknow)
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.historic_data_download import update_data
from corestrategy.strategy_sma import calc_actual_signals_sma
from corestrategy.strategy_rsi import calc_actual_signals_rsi
from corestrategy.delivery_boy import run_delivery_boy
from corestrategy.settings import columns_rsi


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


def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    n = 0
    queue1 = Queue()

    update_data()

    # Пустые DataFrame
    df_previous_sma_50_200 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_30_90 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_20_60 = DataFrame(columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_list = [df_previous_sma_50_200, df_previous_sma_30_90, df_previous_sma_20_60]

    while True:
        if market_is_closed() and not is_time_to_download_data():
            print(f'Market is closed now. Now-time: {_msknow()}')
            wait_until_download_time()
        elif is_time_to_download_data():
            print(f'Time to download data. Now-time: {_msknow()}')
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
