"""Код написан на основе документации API https://tinkoff.github.io/investAPI/
В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
Figi - это уникальный ID акции"""
import asyncio
from typing import Tuple, Union

from dateutil.tz import tzutc
from datetime import datetime, timedelta
from tinkoff.invest import Client, CandleInterval, AsyncClient

from dtb.settings import INVEST_TOKEN
from corestrategy.utils import now_msk, retry_with_timeout, Limit, historic_data_is_actual, timer
from tgbot.models import HistoricCandle, Share


# @retry_with_timeout(60)
async def download_shares() -> None:
    """Позволяет получить из API список всех акций и их параметров"""

    with Client(INVEST_TOKEN) as client:
        api_share_list = client.instruments.shares().instruments

    api_figi_set = set(share.figi for share in api_share_list)
    figi_not_in_api = api_figi_set - await Share.get_all_figi_set()
    await Share.share_not_in_api_update(figi_not_in_api=figi_not_in_api)
    await Share.bulk_update_or_create(share_list=api_share_list)

    print('✅Downloaded list of shares')


# @retry_with_timeout(60)
@Limit(calls=1, period=60)
async def download_candles_by_figi(
        figi: str,
        days: int,
        interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY):
    """Запрашивает и сохраняет свечи по ОДНОМУ str(figi)"""

    now_date = now_msk() - timedelta(
        hours=now_msk().hour - 5,  # TODO почему 5 ?
        minutes=now_msk().minute,
        seconds=now_msk().second,
        microseconds=now_msk().microsecond
    )
    date_from = now_date - timedelta(days=days) + timedelta(days=1)
    date_to = now_msk() + timedelta(days=1)  # TODO refactor

    candles_set = set()
    async with AsyncClient(INVEST_TOKEN) as client:
        async for candle in client.get_all_candles(
            figi=figi,
            from_=date_from,
            to=date_to,
            interval=interval,  # запрашиваемый интервал свеч
        ):
            candles_set.add(candle)

    await Share.async_bulk_add_hist_candles(candles=candles_set, figi=figi, interval=interval)


async def download_historic_candles(figi: Union[Tuple[str], str]):
    """
    Позволяет загрузить ОТСУТСТВУЮЩИЕ свечи из API в БД для одной или множества бумаг.

    :param figi: Одна или множество бумаг, по которым будет запрос к API
    """

    max_days_available_by_api = 366

    print('⏩Downloading historic candles for', figi)
    for fig in [figi]:
        last_date = (await HistoricCandle.get_last_datetime(figi=fig) or
                     datetime(year=2012, month=1, day=1, tzinfo=tzutc()))
        passed_days = (now_msk() - last_date).days
        if passed_days == 0:  # проверка: не запрашиваем ли существующие в CSV данные
            continue
        print('awaiting candles for', fig)
        await download_candles_by_figi(figi=fig, days=passed_days)
        print('got candles for', fig)
        if passed_days > max_days_available_by_api:
            await asyncio.sleep(delay=3)

    print('✅Successfully downloaded and saved historic candles')


@timer
async def get_figi_with_inactual_historic_data(cls, period: int = None) -> Tuple[str]:
    """
    Проверяет актуальны ли данные в таблице БД

    :param cls: указывает на класс, таблица которого будет проверена на актуальность.
    :param period: указывает период расчета индикатора (например: 50 для проверки sma за 50 дней).
    :return: возвращает кортеж figi с неактуальными данными.
    """

    figi_set = await Share.get_all_figi_set()

    async def apply_filter(figi) -> bool:
        args = [arg for arg in [period, figi] if arg]  # берем только not None args (period или figi)
        return not await historic_data_is_actual(cls, *args)

    async def async_filter(async_func, figi):
        if await async_func(figi):
            return figi

    # gather создаёт для каждого figi свой async Task, внутри которого вызывается async_filter, которая применяет
    # переданную функцию фильтрации (apply_filter) для переданного figi (параметра)
    figi_with_inactual_data: Tuple = await asyncio.gather(*[async_filter(apply_filter, figi) for figi in figi_set])
    return figi_with_inactual_data
