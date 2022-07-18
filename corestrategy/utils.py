from os.path import exists
from datetime import time, datetime
from datetime import timedelta as td
from threading import Event

from pandas import DataFrame, concat, DatetimeIndex

from corestrategy.settings import columns_rsi, columns_sma


def _now() -> datetime:
    return datetime.utcnow() + td(hours=3)


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
    return time(hour=7) < _now().time() < time(hour=10)


def market_is_closed() -> bool:
    """Проверяет, закрыта ли биржа"""
    if _now().isoweekday() == 6:
        return time(hour=1, minute=45) < _now().time() < time(hour=23, minute=59, second=59)
    elif _now().isoweekday() == 7:
        return True
    else:
        return time(hour=1, minute=45) < _now().time() < time(hour=10)


def wait_until_download_time() -> None:
    """Помогает остановить поток до тех пор, пока не настанет время обновить исторические данные"""

    hours_now_in_seconds = _now().hour * 3600
    minutes_now_in_seconds = _now().minute * 60
    seconds_now = _now().second

    if _now().isoweekday() == 6:
        timeout = hours_7 + hours_48 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
        print('Strategies wait until 7am Monday. Timeout in seconds:', timeout, 'Now-time:', _now())
        Event().wait(timeout=timeout)

    elif _now().isoweekday() == 7:
        timeout = hours_7 + hours_24 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
        print('Strategies wait until 7am Monday. Timeout in seconds:', timeout, 'Now-time:', _now())
        Event().wait(timeout=timeout)

    else:
        timeout = 36000 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
        if timeout < 0:
            timeout = 0
            print('Strategies wait until 7am today. Timeout in seconds:', timeout, 'Now-time:', _now())
        Event().wait(timeout=timeout)


def wait_until_market_is_open() -> None:
    """Помогает остановить поток до тех пор, пока не откроется биржа"""

    hours_now_in_seconds = _now().hour * 3600
    minutes_now_in_seconds = _now().minute * 60
    seconds_now = _now().second

    timeout = 36000 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
    if timeout < 0:
        timeout = 0
    print('Strategies wait until 10am today. Timeout in seconds:', timeout, 'Now-time:', _now())
    Event().wait(timeout=timeout)


def save_signal_to_df(buy_flag: int,
                      sell_flag: int,
                      last_price: float,
                      figi: str,
                      date: datetime,
                      strategy: str,
                      df_shares: DataFrame,
                      df: DataFrame,
                      rsi_float: float = None) -> DataFrame:
    """Помогает сохранить множество строк с сигналами в один DataFrame"""

    try:
        profit = 0  # profit рассчитывается функцией calc_profit_sma() позже
        ticker = df_shares.loc[df_shares.index == figi].ticker[0]
        share_name = df_shares.loc[df_shares.index == figi].name[0]
        currency = df_shares.loc[df_shares.index == figi].currency[0]
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

    except Exception as e:
        print(e)
        print(figi, _now(), 'in def save_signal_to_df', strategy)

    return df


def historic_data_is_actual(df: DataFrame) -> bool:
    """Позволяет убедиться, что данные в DataFrame актуальны"""

    if type(df.index) == DatetimeIndex:  # проверка является ли DataFrame's index датой и временем
        df_date = df.index.max().date()
    else:
        df_date = df.datetime.max().date()

    return (df_date + td(days=1) >= _now().date() or
            _now().isoweekday() == 7 and df_date + td(days=2) >= _now().date() or
            _now().isoweekday() == 1 and df_date + td(days=3) >= _now().date() or
            _now().isoweekday() == 2 and df_date + td(days=4) >= _now().date() and time() < _now().time() < time(hour=7)
            )


def get_n_digits(number):
    s = str(number)
    if '.' in s:
        return abs(s.find('.') - len(s)) - 1
    else:
        return 0


hours_7 = 25201  # seconds
hours_24 = 86400  # seconds
hours_48 = 172800  # seconds
