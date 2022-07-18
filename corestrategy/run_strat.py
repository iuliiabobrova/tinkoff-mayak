from typing import List
from time import perf_counter

from threading import Event
from pandas import DataFrame

from corestrategy.utils import (is_time_to_download_data,
                                market_is_closed,
                                wait_until_download_time,
                                wait_until_market_is_open,
                                _now)
from corestrategy.actual_data_download import get_all_lasts
from corestrategy.historic_data_download import update_data
from corestrategy.strategy_sma import calc_actual_signals_sma
from corestrategy.strategy_rsi import calc_actual_signals_rsi


def calc_strategies(figi_list: List,
                    df_shares: DataFrame,
                    df_historic_signals_sma: DataFrame,
                    df_historic_signals_rsi: DataFrame,
                    df_close_prices: DataFrame,
                    df_previous_sma: DataFrame,
                    df_historic_sma: DataFrame,
                    n: int,
                    ) -> List:
    start_time = perf_counter()

    df_all_lasts = get_all_lasts(figi_list=figi_list)
    [df_historic_signals_sma,
     df_previous_sma] = calc_actual_signals_sma(n=n, df_shares=df_shares, df_hist_signals_sma=df_historic_signals_sma,
                                                df_all_lasts=df_all_lasts,
                                                df_historic_sma=df_historic_sma, df_previous_sma=df_previous_sma)

    df_historic_signals_rsi = calc_actual_signals_rsi(df_shares=df_shares, figi_list=figi_list,
                                                      df_hist_sgnls=df_historic_signals_rsi, df_all_lasts=df_all_lasts,
                                                      df_close_prices=df_close_prices)

    n += 1  # TODO refactor
    run_time = perf_counter() - start_time
    if run_time < 60:
        Event().wait(timeout=60 - run_time)

    return [df_historic_signals_rsi, df_historic_signals_sma, df_previous_sma, n]


def run_strategies() -> None:
    """Функция для ограничения работы стратегий во времени"""

    n = 0  # TODO refactor (n используется в def calc_actual_signals_sma для изменения первой итерации цикла)

    [figi_list, df_shares, df_close_prices,
     df_historic_signals_sma, df_historic_signals_rsi, df_sma] = update_data()

    df_previous_sma = DataFrame(index=figi_list, columns=['previous_short_sma', 'previous_long_sma'])

    while True:
        if market_is_closed():
            #print(f'Market is closed now. Now-time: {_now()}')
            wait_until_download_time()
        elif is_time_to_download_data():
            #print(f'Time to download data. Now-time: {_now()}')
            [figi_list, df_shares, df_close_prices,
             df_historic_signals_sma, df_historic_signals_rsi, df_sma] = update_data()
            wait_until_market_is_open()
        while not market_is_closed():
            [df_historic_signals_rsi,
             df_historic_signals_sma,
             df_previous_sma,
             n] = calc_strategies(figi_list=figi_list,
                                  df_shares=df_shares,
                                  df_historic_signals_sma=df_historic_signals_sma,
                                  df_historic_signals_rsi=df_historic_signals_rsi,
                                  n=n,
                                  df_close_prices=df_close_prices,
                                  df_previous_sma=df_previous_sma,
                                  df_historic_sma=df_sma)
