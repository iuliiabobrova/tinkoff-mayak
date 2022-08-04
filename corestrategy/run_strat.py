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
                                _now)
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.historic_data_download import update_data
from corestrategy.strategy_sma import calc_actual_signals_sma
from corestrategy.strategy_rsi import calc_actual_signals_rsi
from corestrategy.delivery_boy import run_delivery_boy
from corestrategy.settings import columns_rsi


# TODO Разделить на SMA и RSI
def calc_strategies(figi_list: List,
                    df_shares: DataFrame,
                    df_historic_signals_sma_list: List,
                    df_historic_signals_rsi: DataFrame,
                    df_close_prices: DataFrame,
                    df_previous_sma_list: DataFrame,
                    df_historic_sma_list: List,
                    n: int,
                    df_rsi: DataFrame,
                    queue: Queue) -> List:

    start_time = perf_counter()
    df_all_lasts = get_all_lasts(figi_list=figi_list)
    df_actual_signals = DataFrame(columns=columns_rsi)

    [df_historic_signals_sma_50_200,
     df_previous_sma_50_200,
     df_actual_sgnls_sma_50_200] = calc_actual_signals_sma(
        n=n,
        df_shares=df_shares,
        df_hist_signals_sma=df_historic_signals_sma_list[0],
        df_all_lasts=df_all_lasts,
        df_historic_sma=df_historic_sma_list[0],
        df_previous_sma=df_previous_sma_list[0],
        sma_periods=sma_cross_periods_50_200,
        df_actual_signals=df_actual_signals
    )
    [df_historic_signals_sma_30_90,
     df_previous_sma_30_90,
     df_actual_sgnls_sma_30_90] = calc_actual_signals_sma(
        n=n,
        df_shares=df_shares,
        df_hist_signals_sma=df_historic_signals_sma_list[1],
        df_all_lasts=df_all_lasts,
        df_historic_sma=df_historic_sma_list[1],
        df_previous_sma=df_previous_sma_list[1],
        sma_periods=sma_cross_periods_30_90,
        df_actual_signals=df_actual_signals
    )
    [df_historic_signals_sma_20_60,
     df_previous_sma_20_60,
     df_actual_sgnls_sma_20_60] = calc_actual_signals_sma(
        n=n,
        df_shares=df_shares,
        df_hist_signals_sma=df_historic_signals_sma_list[2],
        df_all_lasts=df_all_lasts,
        df_historic_sma=df_historic_sma_list[2],
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
        df_shares=df_shares,
        df_hist_sgnls=df_historic_signals_rsi,
        df_all_lasts=df_all_lasts,
        df_close_prices=df_close_prices,
        df_rsi=df_rsi,
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

    return [df_historic_signals_rsi, df_historic_signals_sma_list, df_previous_sma_list, n, queue]


def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    n = 0
    queue1 = Queue()

    [figi_list,
     df_shares,
     df_close_prices,
     df_historic_signals_sma_list,
     df_historic_signals_rsi,
     df_sma_list,
     df_rsi] = update_data()

    # Пустые DataFrame
    df_previous_sma_50_200 = DataFrame(index=figi_list, columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_30_90 = DataFrame(index=figi_list, columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_20_60 = DataFrame(index=figi_list, columns=['previous_short_sma', 'previous_long_sma'])
    df_previous_sma_list = [df_previous_sma_50_200, df_previous_sma_30_90, df_previous_sma_20_60]

    while True:
        if market_is_closed() and not is_time_to_download_data():
            print(f'Market is closed now. Now-time: {_now()}')
            wait_until_download_time()
        elif is_time_to_download_data():
            print(f'Time to download data. Now-time: {_now()}')
            [figi_list,
             df_shares,
             df_close_prices,
             df_historic_signals_sma_list,
             df_historic_signals_rsi,
             df_sma_list,
             df_rsi] = update_data()
            wait_until_market_is_open()
        while not market_is_closed():
            [df_historic_signals_rsi,
             df_historic_signals_sma_list,
             df_previous_sma_list,
             n,
             queue1
             ] = calc_strategies(
                figi_list=figi_list,
                df_shares=df_shares,
                df_historic_signals_sma_list=df_historic_signals_sma_list,
                df_historic_signals_rsi=df_historic_signals_rsi,
                n=n,
                df_close_prices=df_close_prices,
                df_previous_sma_list=df_previous_sma_list,
                df_historic_sma_list=df_sma_list,
                df_rsi=df_rsi,
                queue=queue1
            )
