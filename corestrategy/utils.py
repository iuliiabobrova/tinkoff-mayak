from os.path import exists
from datetime import time, datetime
from typing import List

from pandas import DataFrame, concat

from corestrategy.settings import columns_rsi, columns_sma


def check_all_files_existing() -> bool:
    """Проверяет, существуют ли все необходимые файлы"""

    files = ['csv/amount_sma.csv',
             'csv/historic_close_prices.csv',
             'csv/historic_profit_rsi.csv',
             'csv/historic_profit_sma.csv',
             'csv/historic_signals_rsi.csv',
             'csv/historic_signals_sma.csv',
             'csv/historic_volumes.csv',
             'csv/shares.csv',
             'csv/sma.csv',
             'csv/std.csv']

    return all(map(lambda file: exists(file), files))


def is_time_to_download_data() -> bool:
    """Проверяет, подходит ли время для объемной загрузки исторических данных"""
    return time(hour=7) < datetime.now().time() < time(hour=10)


def market_is_open() -> bool:
    """Проверяет, открыта ли биржа"""
    return time(hour=10) < datetime.now().time() < time(hour=1, minute=45)


def check_df_size_and_save(df_list: List, signal: DataFrame):
    """Временно не используется"""
    for i in df_list:
        if df_list[i].index.max() < 5000 or df_list[i].empty is True:
            df_list[i] = concat([df_list[i], signal], ignore_index=True, copy=False)
            return df_list


def save_signal_to_df(buy_flag: int,
                      sell_flag: int,
                      x: int or str,
                      last_price: float,
                      figi: str,
                      date: datetime,
                      strategy: str,
                      df_shares: DataFrame,
                      df: DataFrame = None,
                      rsi_float: float = None) -> DataFrame:
    """Помогает сохранить множество строк с сигналами в один DataFrame"""

    profit = 0  # profit рассчитывается функцией calc_profit_sma() позже
    ticker = df_shares.ticker[x]
    share_name = df_shares.name[x]
    currency = df_shares.currency[x]
    if strategy == 'sma':
        df = concat(objs=[df, (DataFrame(data=[[figi,
                                                ticker,
                                                share_name,
                                                date,
                                                last_price,
                                                sell_flag,
                                                buy_flag,
                                                strategy,
                                                profit,
                                                currency]], columns=columns_sma))],
                    ignore_index=True, copy=False)
    if strategy == 'rsi':
        df = concat(objs=[df, (DataFrame(data=[[figi,
                                                ticker,
                                                share_name,
                                                date,
                                                last_price,
                                                rsi_float,
                                                sell_flag,
                                                buy_flag,
                                                'rsi',
                                                profit,
                                                currency]], columns=columns_rsi))],
                    ignore_index=True, copy=False)

    return df
