# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции
import asyncio

from dateutil.tz import tzutc
from datetime import datetime, timedelta
from tinkoff.invest import Client, CandleInterval
from toolz import unique
from tqdm import tqdm

from dtb.settings import INVEST_TOKEN
from corestrategy.hitoric_data_calc import recalc_sma_if_inactual, get_or_calc_sma_historic_signals
from corestrategy.settings import *
from corestrategy.utils import now_msk, retry_with_timeout, Limit, \
    get_figi_list_with_inactual_historic_data
from tgbot.models import HistoricCandle, Share


@retry_with_timeout(60)
def download_shares() -> None:
    """Позволяет получить из API список всех акций и их параметров"""

    with Client(INVEST_TOKEN) as client:
        for share in client.instruments.shares().instruments:
            Share.delete_and_create(share=share)

    print('✅Downloaded list of shares')


@Limit(calls=299, period=60)  # API позволяет запрашивать свечи не более 300 раз в минуту
@retry_with_timeout(60)
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

    await HistoricCandle.async_create(candles=candles_list, figi=figi, interval='day')


async def download_historic_candles(figi_list: List):
    """Позволяет загрузить исторические свечи из API в БД"""

    max_days_available_by_api = 366

    print('⏩Downloading historic candles for', len(figi_list), 'shares')
    for i in tqdm(range(len(figi_list))):
        figi = figi_list[i]
        last_date = await HistoricCandle.get_last_datetime(figi=figi) or \
                    datetime(year=2012, month=1, day=1, tzinfo=tzutc())
        passed_days = (now_msk() - last_date).days
        if passed_days == 0:  # проверка: не запрашиваем ли существующие в CSV данные
            continue
        await download_candles_by_figi(figi=figi, days=passed_days)
        if passed_days > max_days_available_by_api:
            await asyncio.sleep(delay=3)

    print('✅Successfully downloaded and saved historic candles')


def update_data():
    """Функция обновляет все исторические данные: Share, HistoricCandle, MovingAverage, RSI, Signal"""
    print('⏩START DATA CHECK. It can take 2 hours')

    download_shares()
    figi_list = get_figi_list_with_inactual_historic_data(HistoricCandle)[:3]
    asyncio.run(download_historic_candles(figi_list=figi_list))
    recalc_sma_if_inactual()
    for periods in sma_cross_periods_all:
        get_or_calc_sma_historic_signals(sma_periods=periods)

    # # проверка rsi-signals на актуальность
    # if exists(path='csv/historic_signals_rsi.csv'):
    #     df = read_csv(
    #         filepath_or_buffer='csv/historic_signals_rsi.csv',
    #         sep=';',
    #         index_col=0,
    #         parse_dates=['datetime'],
    #         low_memory=False
    #     )
    #     if historic_data_is_actual(df=df):
    #         df_historic_signals_rsi = df
    #         df_rsi = read_csv(
    #             filepath_or_buffer='csv/rsi.csv',
    #             sep=';',
    #             index_col=0
    #         )
    #     else:
    #         save_historic_signals_rsi()
    # else:
    #     save_historic_signals_rsi()
    # calc_std(df_close_prices=df_close_prices) TODO (пока не используется)
    # calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)  TODO RSI-profit
    print('✅All data is actual')
