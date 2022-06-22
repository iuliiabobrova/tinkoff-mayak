from os.path import exists


def check_files_existing() -> bool:
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
