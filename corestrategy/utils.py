import asyncio
import functools
from asyncio import sleep as asyncsleep
from datetime import time, datetime
from datetime import timedelta as td
from threading import Event
from time import perf_counter, monotonic
from typing import List, Optional

from dateutil.tz import tzutc
from pandas import DataFrame, concat

from corestrategy.settings import columns_rsi, columns_sma
from tgbot.models import Share
from tgbot.static_text import sma_50_200_is_chosen, sma_30_90_is_chosen, sma_20_60_is_chosen, rsi_is_chosen


def now_msk() -> datetime:
    return datetime.now(tz=tzutc()).replace(microsecond=0) + td(hours=3)


def is_time_to_download_data() -> bool:
    """Проверяет, подходит ли время для объемной загрузки исторических данных"""
    value = time(hour=7) < now_msk().time() < time(hour=10)
    return value


def market_is_closed() -> bool:
    """Проверяет, закрыта ли биржа"""
    if now_msk().isoweekday() == 6:
        value = time(hour=1, minute=45) < now_msk().time() < time(hour=23, minute=59, second=59)
        return value
    elif now_msk().isoweekday() == 7:
        return True
    else:
        value = time(hour=1, minute=45) < now_msk().time() < time(hour=10)
        return value


def wait_until_download_time() -> None:
    """Помогает остановить поток до тех пор, пока не настанет время обновить исторические данные"""

    hours_7 = 25201  # seconds
    hours_24 = 86400  # seconds
    hours_48 = 172800  # seconds

    hours_now_in_seconds = now_msk().hour * 3600
    minutes_now_in_seconds = now_msk().minute * 60
    seconds_now = now_msk().second

    if now_msk().isoweekday() == 6:
        timeout = hours_7 + hours_48 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
        print('Strategies wait until 7am Monday. Timeout in seconds:', timeout, 'Now-time:', now_msk())
        Event().wait(timeout=timeout)

    elif now_msk().isoweekday() == 7:
        timeout = hours_7 + hours_24 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
        print('Strategies wait until 7am Monday. Timeout in seconds:', timeout, 'Now-time:', now_msk())
        Event().wait(timeout=timeout)

    else:
        timeout = hours_7 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
        print('Strategies wait until 7am today. Timeout in seconds:', timeout, 'Now-time:', now_msk())
        Event().wait(timeout=timeout)


def wait_until_market_is_open() -> None:
    """Помогает остановить поток до тех пор, пока не откроется биржа"""

    hours_now_in_seconds = now_msk().hour * 3600
    minutes_now_in_seconds = now_msk().minute * 60
    seconds_now = now_msk().second

    timeout = 36000 - (hours_now_in_seconds + minutes_now_in_seconds + seconds_now)
    if timeout < 0:
        timeout = 0
    print('Strategies wait until 10am today. Timeout in seconds:', timeout, 'Now-time:', now_msk())
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


def start_of_current_day() -> datetime:
    today = datetime.utcnow().date()
    return datetime(today.year, today.month, today.day, tzinfo=tzutc())


def historic_data_is_actual(cls, figi: str = None, period: int = None) -> bool:
    """Позволяет убедиться, что данные в БД актуальны"""

    args = [arg for arg in [figi, period] if arg]
    date_time = asyncio.run(cls.get_last_datetime(*args))

    if date_time is None:
        return False
    market_hour = start_of_current_day() + td(hours=1, minutes=45)
    return (
            date_time + td(days=1) >= start_of_current_day() + td(hours=1, minutes=45) or
            now_msk().isoweekday() == 7 and date_time + td(days=2) >= market_hour or
            now_msk().isoweekday() == 1 and date_time + td(days=3) >= market_hour or
            now_msk().isoweekday() == 2 and date_time + td(days=4) >= market_hour and time() < now_msk().time() < time(hour=7)
    )


def get_n_digits(number):
    """Помогает определить количество знаков после точки в number"""

    s = str(number)
    if '.' in s:
        return abs(s.find('.') - len(s)) - 1
    else:
        return 0


def convert_string_price_into_int_or_float(price: str) -> float or int:
    """Помогает конвертировать str в int или float"""

    n_digits = get_n_digits(price)
    if float(price) // 1 == float(price):
        price = int(float(price))
    elif price == 0 or price is None:
        price = 0
    else:
        price = round(float(price), n_digits)
    return price


class Limit(object):
    """Добавить описание декоратора"""  # TODO Добавить описание декоратора

    def __init__(self, calls, period):
        self.calls = calls
        self.period = period
        self.clock = monotonic
        self.last_reset = 0
        self.num_of_calls = 0

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            if self.num_of_calls >= self.calls:
                await asyncsleep(self.__remaining_period())

            remaining_period = self.__remaining_period()

            if remaining_period <= 0:
                self.num_of_calls = 0
                self.last_reset = self.clock()

            self.num_of_calls += 1

            return await func(*args, **kwargs)

        return wrapper

    def __remaining_period(self):
        elapsed = self.clock() - self.last_reset
        return self.period - elapsed


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


# TODO мб удалить при отстутсвии необходимости
def timer(func):
    """Декоратор считает сколько времени затрачено на функцию"""

    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        runtime = perf_counter() - start
        print(func, 'took', runtime, 'seconds')
        if result is None:
            return
        else:
            return result

    return _wrapper


@timer
def get_figi_list_with_inactual_historic_data(cls, period: int = None) -> List[str]:
    def apply_filter(figi: str):
        args = [arg for arg in [period, figi] if arg]
        return not historic_data_is_actual(cls, *args)

    return list(filter(lambda figi: apply_filter(figi), Share.get_figi_list()))
