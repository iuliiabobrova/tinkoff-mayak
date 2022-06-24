from os.path import exists
from typing import Tuple
from time import perf_counter

from threading import Event
from pandas import DataFrame, read_csv

from corestrategy.strategy_rsi import calc_actual_signals_rsi, columns_rsi
from corestrategy.strategy_sma import calc_actual_signals_sma, columns_sma
from corestrategy.utils import market_is_closed
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.deliery_boy import run_delivery_boy
from corestrategy.historic_data_download import run_download_data


def dataframe_preparation() -> Tuple[DataFrame, DataFrame, DataFrame, DataFrame]:
    df_historic_signals_rsi = read_csv(filepath_or_buffer='csv/historic_signals_rsi.csv',
                                       sep=';',
                                       parse_dates=['datetime'],
                                       index_col=0)
    df_historic_signals_sma = read_csv(filepath_or_buffer='csv/historic_signals_sma.csv',
                                       sep=';',
                                       index_col=0)
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

    return df_historic_signals_rsi, df_historic_signals_sma, df_actual_signals_rsi, df_actual_signals_sma


def run_strategies(figi_list: list, df_shares: DataFrame) -> None:
    """Функция создана для ограничения работы стратегий во времени"""

    previous_size_df_sma = 9999999
    previous_size_df_rsi = 9999999

    [df_historic_signals_rsi,
     df_historic_signals_sma,
     df_actual_signals_rsi,
     df_actual_signals_sma] = dataframe_preparation()

    n = 0  # TODO refactor (n используется в def calc_actual_signals_sma для изменения первой итерации цикла)

    while True:
        if market_is_closed():
            run_download_data()
        else:
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
                                                                df_all_lasts=df_all_lasts)

            run_delivery_boy(df_rsi=df_actual_signals_rsi,
                             df_sma=df_actual_signals_sma,
                             previous_size_df_sma=previous_size_df_sma,
                             previous_size_df_rsi=previous_size_df_rsi)
            n += 1  # TODO refactor
            run_time = perf_counter() - start_time
            if run_time < 60:
                Event().wait(timeout=60-run_time)
