from os.path import exists
from datetime import time, datetime


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


def time_to_download_data() -> bool:
    return time(hour=1, minute=45) < datetime.now().time() < time(hour=5)


def market_is_open() -> bool:
    return time(hour=7) < datetime.now().time() < time(hour=1, minute=45)
