from os.path import exists
from typing import Tuple, List
from time import perf_counter

from threading import Event
from pandas import DataFrame, read_csv

from corestrategy.utils import is_time_to_download_data, market_is_closed, wait_10am_msc
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.deliery_boy import run_delivery_boy
from corestrategy.historic_data_download import update_data
from corestrategy.settings import columns_sma, columns_rsi
from corestrategy.strategy_sma import calc_actual_signals_sma
from corestrategy.strategy_rsi import calc_actual_signals_rsi


def dataframe_preparation() -> Tuple[DataFrame, DataFrame]:
    if exists('csv/actual_signals_rsi.csv'):
        df_actual_signals_rsi = read_csv(filepath_or_buffer='csv/actual_signals_rsi.csv',
                                         sep=';',
                                         index_col=0)
    else:
        df_actual_signals_rsi = DataFrame(columns=columns_rsi)  # пустой DF
    if exists('csv/actual_signals_sma.csv'):
        df_actual_signals_sma = read_csv(filepath_or_buffer='csv/actual_signals_sma.csv',
                                         sep=';',
                                         index_col=0)
    else:
        df_actual_signals_sma = DataFrame(columns=columns_sma)  # пустой DF

    return df_actual_signals_rsi, df_actual_signals_sma


def calc_strategies(figi_list: List,
                    df_shares: DataFrame,
                    df_historic_signals_sma: DataFrame,
                    df_historic_signals_rsi: DataFrame,
                    df_close_prices: DataFrame,
                    df_actual_signals_sma: DataFrame,
                    df_actual_signals_rsi: DataFrame,
                    n: int,
                    previous_size_df_sma: int,
                    previous_size_df_rsi: int) -> Tuple[int, int, DataFrame, DataFrame, DataFrame, DataFrame, int]:
    start_time = perf_counter()

    df_all_lasts = get_all_lasts(figi_list=figi_list)
    [df_actual_signals_sma,
     df_historic_signals_sma] = calc_actual_signals_sma(n=n,
                                                        figi_list=figi_list,
                                                        df_shares=df_shares,
                                                        df_historic_signals_sma=df_historic_signals_sma,
                                                        df_actual_signals_sma=df_actual_signals_sma,
                                                        df_all_lasts=df_all_lasts)
    [df_actual_signals_rsi,
     df_historic_signals_rsi] = calc_actual_signals_rsi(df_shares=df_shares,
                                                        figi_list=figi_list,
                                                        df_historic_signals_rsi=df_historic_signals_rsi,
                                                        df_actual_signals_rsi=df_actual_signals_rsi,
                                                        df_all_lasts=df_all_lasts,
                                                        df_close_prices=df_close_prices)

    if n != 0:
        [previous_size_df_sma, previous_size_df_rsi] = run_delivery_boy(df_rsi=df_actual_signals_rsi,
                                                                        df_sma=df_actual_signals_sma,
                                                                        previous_size_df_sma=previous_size_df_sma,
                                                                        previous_size_df_rsi=previous_size_df_rsi)
    n += 1  # TODO refactor
    run_time = perf_counter() - start_time
    if run_time < 60:
        Event().wait(timeout=60 - run_time)

    return (previous_size_df_sma, previous_size_df_rsi, df_actual_signals_sma,
            df_actual_signals_rsi, df_historic_signals_rsi, df_historic_signals_sma, n)


def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    previous_size_df_sma = 9999999
    previous_size_df_rsi = 9999999

    [df_actual_signals_rsi,
     df_actual_signals_sma] = dataframe_preparation()

    n = 0  # TODO refactor (n используется в def calc_actual_signals_sma для изменения первой итерации цикла)

    figi_list, df_shares, df_close_prices, df_historic_signals_sma, df_historic_signals_rsi = update_data()

    while True:
        if is_time_to_download_data():
            figi_list, df_shares, df_close_prices, df_historic_signals_sma, df_historic_signals_rsi = update_data()
            wait_10am_msc()
        elif market_is_closed():
            wait_10am_msc()
        while not market_is_closed():
            (previous_size_df_sma,
             previous_size_df_rsi,
             df_actual_signals_sma,
             df_actual_signals_rsi,
             df_historic_signals_sma,
             df_historic_signals_rsi,
             n) = calc_strategies(figi_list=figi_list,
                                  df_shares=df_shares,
                                  df_historic_signals_sma=df_historic_signals_sma,
                                  df_historic_signals_rsi=df_historic_signals_rsi,
                                  n=n,
                                  df_close_prices=df_close_prices,
                                  df_actual_signals_rsi=df_actual_signals_rsi,
                                  df_actual_signals_sma=df_actual_signals_sma,
                                  previous_size_df_sma=previous_size_df_sma,
                                  previous_size_df_rsi=previous_size_df_rsi)
