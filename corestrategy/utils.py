import asyncio
import functools
from asyncio import sleep as asyncsleep
from datetime import time, datetime
from datetime import timedelta
from threading import Event
from time import perf_counter, monotonic

from dateutil.tz import tzutc


def start_of_current_day() -> datetime:
    today = datetime.utcnow().date()
    return datetime(today.year, today.month, today.day, tzinfo=tzutc())


def market_close_time(days_offset: int) -> datetime:
    """1:45 - время закрытия биржи в определенный день.
    :param days_offset: Временной сдвиг (в днях) от сегодняшнего дня (для вчера = -1, сегодня = 0)"""
    return start_of_current_day() + timedelta(hours=1, minutes=45) + timedelta(days=days_offset)


def market_open_time(days_offset: int) -> datetime:
    """10:00 - время открытия биржи в определенный день.
    :param days_offset: Временной сдвиг (в днях) от сегодняшнего дня (для вчера = -1, сегодня = 0)"""
    return start_of_current_day() + timedelta(hours=10) + timedelta(days=days_offset)


def now_msk() -> datetime:
    return datetime.now(tz=tzutc()).replace(microsecond=0) + timedelta(hours=3)


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


def normal_timedelta_from_last_candle() -> timedelta:
    """Позволяет определить временной разрыв между актуальной ДНЕВНОЙ свечой и текущим временем"""
    if now_msk().isoweekday() == 7:
        return timedelta(days=2)
    elif now_msk().isoweekday() == 1:
        return timedelta(days=3)
    elif now_msk().isoweekday() == 2 and now_msk() < market_close_time(days_offset=0):
        return timedelta(days=4)
    else:
        return timedelta(days=1)


def minutes_timedelta_from_last_candle() -> timedelta:  # TODO need test
    """Позволяет определить временной разрыв между актуальной МИНУТНОЙ свечой и текущим временем"""
    if market_close_time(days_offset=0) < now_msk() < market_open_time(days_offset=0):  # от закрытия до открытия биржи
        return now_msk() - market_close_time(days_offset=0)
    elif now_msk().isoweekday() == 7:  # если воскресенье
        return now_msk() - market_close_time(days_offset=-1)
    elif now_msk().isoweekday() == 1 and start_of_current_day() < now_msk() < market_open_time(days_offset=0):
        # если понедельник, время до открытия биржи
        return now_msk() - market_close_time(days_offset=-2)
    else:
        return now_msk() - (now_msk() - timedelta(minutes=1))  # гэп в 1 минуту = норма


async def historic_data_is_actual(cls, figi: str = None, period: int = None) -> bool:
    """
    :param cls: класс, таблица которого проверяется на актуальность.
    :param figi: figi акции, которая проверяется в таблице. Если figi не задан, проверяются все figi.
    :param period: передается для проверки только определенного периода индикатора.
    Если не задан, будут проверены все периоды индикатора в таблице.
    :return: Возвращает True в случае, если исторические данные актуальны.
    """

    args = [arg for arg in [figi, period] if arg]
    last_candle_datetime = await cls.get_last_datetime(*args)
    if last_candle_datetime is None:
        return False

    print(figi)  # TODO delete
    print('last_candle_datetime', last_candle_datetime)  # TODO delete
    print('days_timedelta_from_last_candle()', normal_timedelta_from_last_candle())  # TODO delete
    print('market_close_time(days_offset=0)', market_close_time(days_offset=0))  # TODO delete
    print('last_candle_datetime + days_timedelta_from_last_candle()', last_candle_datetime + normal_timedelta_from_last_candle())  # TODO delete
    print('')  # TODO delete

    return last_candle_datetime + normal_timedelta_from_last_candle() >= market_close_time(days_offset=0)


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


# TODO мб удалить при отсутствии необходимости
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


def get_attributes_list(cls):
    class_name = str(cls).split(sep='.')[-1][:-2]
    classname_length = len(class_name) + 1
    return cls.__doc__[classname_length:-1].split(sep=', ')
