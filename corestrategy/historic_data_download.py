"""Код написан на основе документации API https://tinkoff.github.io/investAPI/
В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
Figi - это уникальный ID акции"""
import asyncio
from typing import List

from dateutil.tz import tzutc
from datetime import datetime, timedelta
from tinkoff.invest import Client, CandleInterval
from toolz import unique
from tqdm import tqdm

from dtb.settings import INVEST_TOKEN
from corestrategy.utils import now_msk, retry_with_timeout, Limit, historic_data_is_actual, timer
from tgbot.models import HistoricCandle, Share


# @retry_with_timeout(60)
def download_shares() -> None:
    """Позволяет получить из API список всех акций и их параметров"""

    with Client(INVEST_TOKEN) as client:
        api_share_list = client.instruments.shares().instruments

    api_figi_set = set(share.figi for share in api_share_list)
    print(Share.get_all_figi())
    figi_not_in_api = api_figi_set - set(Share.get_all_figi())
    print('figi_not_in_api:', figi_not_in_api)
    Share.objects.filter(figi__in=figi_not_in_api).update(exists_in_api=False)
    Share.bulk_update_or_create(share_list=api_share_list)

    print('✅Downloaded list of shares')


@Limit(calls=299, period=60)  # API позволяет запрашивать свечи не более 300 раз в минуту
# @retry_with_timeout(60)
async def download_candles_by_figi(
        figi: str,
        days: int,
        interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY):
    """Запрашивает и сохраняет все ОТСУТСТВУЮЩИЕ свечи по ОДНОМУ str(figi)"""

    now_date = now_msk() - timedelta(
        hours=now_msk().hour - 5,  # TODO почему 5 ?
        minutes=now_msk().minute,
        seconds=now_msk().second,
        microseconds=now_msk().microsecond
    )
    date_from = now_date - timedelta(days=days) + timedelta(days=1)
    date_to = now_msk() + timedelta(days=1)  # TODO refactor

    with Client(INVEST_TOKEN) as client:
        candles_generator = client.get_all_candles(
            figi=figi,
            from_=date_from,
            to=date_to,
            interval=interval,  # запрашиваемый интервал свеч
        )
        candles_list = list(unique(candles_generator, key=lambda candle: candle.time))

    await Share.async_bulk_add_hist_candles(candles=candles_list, figi=figi, interval=interval)


async def download_historic_candles(figi_list: List):
    """Позволяет загрузить ОТСУТСТВУЮЩИЕ свечи из API в БД"""

    max_days_available_by_api = 366

    print('⏩Downloading historic candles for', len(figi_list), 'shares')
    for i in tqdm(range(len(figi_list))):
        figi = figi_list[i]
        last_date = (await HistoricCandle.get_last_datetime(figi=figi) or
                     datetime(year=2012, month=1, day=1, tzinfo=tzutc()))
        passed_days = (now_msk() - last_date).days
        if passed_days == 0:  # проверка: не запрашиваем ли существующие в CSV данные
            continue
        await download_candles_by_figi(figi=figi, days=passed_days)
        if passed_days > max_days_available_by_api:
            await asyncio.sleep(delay=3)

    print('✅Successfully downloaded and saved historic candles')


@timer
def get_figi_list_with_inactual_historic_data(cls, period: int = None) -> List[str]:
    """
    Проверяет актуальны ли данные в таблице БД

    :param cls: указывает на класс, таблица которого будет проверена на актуальность.
    :param period: указывает период расчета индикатора (например: 50 для проверки sma за 50 дней).
    :return: возвращает список figi с неактуальными данными.
    """

    def apply_filter(figi: str):
        args = [arg for arg in [period, figi] if arg]
        return not historic_data_is_actual(cls, *args)

    return list(filter(lambda figi: apply_filter(figi), Share.get_all_figi()))
