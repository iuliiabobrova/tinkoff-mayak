from os.path import exists


# TODO
# можно проще (map и lambda функции, с ними 42-51 можно в одну строчку сделать)
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
    list_of_files_existing = []

    for file in files:
        exist = exists(file)
        list_of_files_existing = list_of_files_existing + [exist]

    if all(list_of_files_existing):
        answer = True
    else:
        answer = False

    return answer
