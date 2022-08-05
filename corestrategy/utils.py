from datetime import time, datetime
from datetime import timedelta as td
from threading import Event
from time import perf_counter
from typing import List, Optional
import functools

from pandas import DataFrame, concat

from corestrategy.settings import columns_rsi, columns_sma
from tgbot.static_text import (
    sma_50_200_is_chosen, rsi_is_chosen, sma_30_90_is_chosen, sma_20_60_is_chosen
)


def _now() -> datetime:
    return datetime.utcnow() + td(hours=3)


class Strategy:
    _all_cases = {
        'rsi': 'RSI',
        'sma_50_200': 'cross-SMA 50-200',
        'sma_30_90': 'cross-SMA 30-90',
        'sma_20_60': 'cross-SMA 20-60'
    }

    def __init__(self, strategy_id: str, strategy_name: Optional[str] = None):
        self.strategy_id = strategy_id
        if strategy_name is None:
            self.strategy_name = Strategy._all_cases[strategy_id]
        else:
            self.strategy_name = strategy_name

    @classmethod
    def sma_50_200(cls) -> object:
        return Strategy(strategy_id='sma_50_200')

    @classmethod
    def sma_30_90(cls) -> object:
        return Strategy(strategy_id='sma_30_90')

    @classmethod
    def sma_20_60(cls) -> object:
        return Strategy(strategy_id='sma_20_60')

    @classmethod
    def rsi(cls) -> object:
        return Strategy(strategy_id='rsi')

    @classmethod
    def all(cls) -> List[object]:
        return [cls.rsi(), cls.sma_50_200(), cls.sma_30_90(), cls.sma_20_60()]

    @classmethod
    def name(cls, strategy_id: str) -> str:
        return cls._all_cases[strategy_id]

    def description(self) -> str:
        if self.strategy_id.startswith('sma_50_200'):
            return sma_50_200_is_chosen
        elif self.strategy_id.startswith('sma_30_90'):
            return sma_30_90_is_chosen
        elif self.strategy_id.startswith('sma_20_60'):
            return sma_20_60_is_chosen
        elif self.strategy_id.startswith('rsi'):
            return rsi_is_chosen


def is_time_to_download_data() -> bool:
    """Проверяет, подходит ли время для объемной загрузки исторических данных"""
    value = time(hour=7) < _now().time() < time(hour=10)
    # print(value)  # log can affect memory
    return value


def market_is_closed() -> bool:
    """Проверяет, закрыта ли биржа"""
    if _now().isoweekday() == 6:
        value = time(hour=1, minute=45) < _now().time() < time(hour=23, minute=59, second=59)
        return value
    elif _now().isoweekday() == 7:
        return True
    else:
        value = time(hour=1, minute=45) < _now().time() < time(hour=10)
        return value


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
        timeout = hours_7 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
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
                      last_price: float,
                      figi: str,
                      date_time: datetime,
                      strategy_id: str,
                      df_shares: DataFrame,
                      df: DataFrame,  # historic_signals
                      df_actual_signals: DataFrame = None,
                      rsi_float: float = None) -> List:
    """Помогает сохранить множество строк с сигналами в один DataFrame"""

    profit = 0  # profit рассчитывается функцией calc_profit_sma() позже
    ticker = df_shares.loc[df_shares.index == figi].ticker[0]
    share_name = df_shares.loc[df_shares.index == figi].name[0]
    currency = df_shares.loc[df_shares.index == figi].currency[0]
    country = df_shares.loc[df_shares.index == figi].country_of_risk[0]
    if strategy_id.startswith('sma'):
        df = concat(
            objs=[df, (DataFrame(data=[[figi,
                                        ticker,
                                        share_name,
                                        date_time,
                                        last_price,
                                        buy_flag,
                                        strategy_id,
                                        profit,
                                        currency,
                                        country]],
                                 columns=columns_sma))],
            ignore_index=True,
            copy=False)
    if strategy_id.startswith('rsi'):
        df = concat(
            objs=[df, (DataFrame(data=[[figi,
                                        ticker,
                                        share_name,
                                        date_time,
                                        last_price,
                                        rsi_float,
                                        buy_flag,
                                        strategy_id,
                                        profit,
                                        currency,
                                        country]],
                                 columns=columns_rsi))],
            ignore_index=True,
            copy=False)

    if df_actual_signals is not None:
        if strategy_id.startswith('sma'):
            df_actual_signals = concat(
                objs=[df_actual_signals, (DataFrame(data=[[figi,
                                                           ticker,
                                                           share_name,
                                                           date_time,
                                                           last_price,
                                                           buy_flag,
                                                           strategy_id,
                                                           profit,
                                                           currency,
                                                           country]],
                                                    columns=columns_sma))],
                ignore_index=True,
                copy=False)
        if strategy_id.startswith('rsi'):
            df_actual_signals = concat(
                objs=[df_actual_signals, (DataFrame(data=[[figi,
                                                           ticker,
                                                           share_name,
                                                           date_time,
                                                           last_price,
                                                           rsi_float,
                                                           buy_flag,
                                                           strategy_id,
                                                           profit,
                                                           currency,
                                                           country]],
                                                    columns=columns_rsi))],
                ignore_index=True,
                copy=False)

    return [df, df_actual_signals]


def historic_data_is_actual(cls) -> bool:
    """Позволяет убедиться, что данные в DataFrame актуальны"""

    date_time = cls.get_last_datetime_by_figi()
    market_hour = _now().date() + td(hours=1, minutes=45)
    return (
            date_time + td(days=1) >= _now().date() + td(hours=1, minutes=45) or
            _now().isoweekday() == 7 and date_time + td(days=2) >= market_hour or
            _now().isoweekday() == 1 and date_time + td(days=3) >= market_hour or
            _now().isoweekday() == 2 and date_time + td(days=4) >= market_hour and time() < _now().time() < time(hour=7)
    )


def get_n_digits(number):
    s = str(number)
    if '.' in s:
        return abs(s.find('.') - len(s)) - 1
    else:
        return 0


def convert_string_price_into_int_or_float(price: str) -> float or int:
    n_digits = get_n_digits(price)
    if float(price) // 1 == float(price):
        price = int(float(price))
    elif price == 0 or price is None:
        price = 0
    else:
        price = round(float(price), n_digits)
    return price


def timer(func):
    """Декоратор считает сколько времени затрачено на функцию"""

    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        runtime = perf_counter() - start
        if result is None:
            return runtime
        else:
            return runtime, result
    return _wrapper


def retry_with_timeout(timeout):
    """Декоратор помогает рекурсивно вызывать функцию в случае ошибки с паузой в timeout-секунд"""

    def retry_decorator(func):
        def _wrapper(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(e)
                    Event().wait(timeout=timeout)
        return _wrapper
    return retry_decorator


hours_7 = 25201  # seconds
hours_24 = 86400  # seconds
hours_48 = 172800  # seconds
