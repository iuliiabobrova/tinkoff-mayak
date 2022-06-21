from threading import Event
from datetime import time, datetime, timedelta
from os import stat
from os.path import exists
from pandas import to_datetime
from pandas import DataFrame, read_csv

from corestrategy.strategy_rsi import calc_actual_signals_rsi, columns_rsi
from corestrategy.strategy_sma import calc_actual_signals_sma, columns_sma
from corestrategy.utils import check_files_existing
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.historic_data_download import data_downloading_flag
# TODO глобальные переменные не требуют импорта?


def dataframe_preparation() -> tuple[DataFrame, DataFrame, DataFrame, DataFrame]:
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

    global data_downloading_flag

    Event().wait(timeout=10)
    n = 0  # TODO refactor
    if check_files_existing() and data_downloading_flag == False:
        # подготовка DataFrame
        [df_historic_signals_rsi,
         df_historic_signals_sma,
         df_actual_signals_rsi,
         df_actual_signals_sma] = dataframe_preparation()

        while True:
            mod_date = datetime.now() - to_datetime(stat('csv/sma.csv').st_mtime_ns)
            if (not time(hour=3) < datetime.now().time() < time(hour=6)) and \
               (mod_date < timedelta(hours=24)):

                print('strategies_calc_starts')
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
                n += 1  # TODO refactor
                Event().wait(60)

            else:
                n = 0  # TODO refactor
                Event().wait(240)
    else:
        Event().wait(240)
        run_strategies(figi_list, df_shares)
