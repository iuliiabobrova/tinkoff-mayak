# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции
import asyncio
from os.path import exists, getmtime
from threading import Event

from asgiref.sync import sync_to_async
from pandas import read_csv, to_datetime
from datetime import datetime, timedelta
from tinkoff.invest import Client, CandleInterval

from dtb.settings import INVEST_TOKEN
from corestrategy.hitoric_data_calc import calc_historic_signals_sma, calc_sma, save_historic_signals_rsi
from corestrategy.settings import *
from corestrategy.utils import historic_data_is_actual, _now, retry_with_timeout, Limit
from tgbot.models import HistoricCandle, Share, MovingAverage


@retry_with_timeout(60)
def download_shares() -> None:
    """Позволяет получить из API список всех акций и их параметров"""

    with Client(INVEST_TOKEN) as client:
        for share in client.instruments.shares().instruments:
            Share.delete_and_create(share=share)

    print('✅Downloaded list of shares')


@Limit(calls=299, period=60)  # API позволяет запрашивать свечи не более 300 раз в минуту
#@retry_with_timeout(60)
async def download_candles_by_figi(
        figi: str,
        days: int,
        interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY):
    """Запрашивает все ОТСУТСТВУЮЩИЕ свечи по ОДНОМУ str(figi)"""

    now_date = _now() - timedelta(
        hours=_now().hour - 5,  # TODO почему 5 ?
        minutes=_now().minute,
        seconds=_now().second,
        microseconds=_now().microsecond
    )
    date_from = now_date - timedelta(days=days) + timedelta(days=1)
    date_to = _now() + timedelta(days=1)  # TODO refactor

    print('date_from:', date_from)

    with Client(INVEST_TOKEN) as client:
        candles = client.get_all_candles(
            figi=figi,  # сюда должен поступать только один figi (id акции)
            from_=date_from,  # int, кол-во дней назад
            to=date_to,
            interval=interval,  # запрашиваемая размерность свеч
        )
        for candle in candles:
            print(f"Creating {figi}...")
            await HistoricCandle.async_create(candle=candle, figi=figi, interval='day')


async def download_historic_candles(figi_list: List):
    """Позволяет загрузить исторические свечи из АПИ в БД"""

    max_days_available_by_api = 366

    print('⏩Downloading historic candles')
    for figi in figi_list:
        last_date = await HistoricCandle.get_last_datetime(figi=figi) or datetime(year=2012, month=1, day=1)
        passed_days = (_now() - last_date).days
        print(f"passed_days = {passed_days}")
        if passed_days == 0:  # проверка: не запрашиваем ли существующие в CSV данные
            continue
        print('start def download by figi')
        await download_candles_by_figi(figi=figi, days=passed_days)
        if passed_days > max_days_available_by_api:
            Event().wait(timeout=3)

    print('✅Successfully downloaded and saved historic candles')


# проверка sma на актуальность
def recalc_sma_if_inactual(sma_periods: SMACrossPeriods):
    if not historic_data_is_actual(MovingAverage):  # TODO check parameter
        calc_sma(sma_periods=sma_periods)


# проверка sma-signals на актуальность
def get_or_calc_sma_historic_signals(sma_periods: SMACrossPeriods):
    file_path = f'csv/historic_signals_sma_{sma_periods.short}_{sma_periods.long}.csv'
    if exists(path=file_path):
        df = read_csv(
            filepath_or_buffer=file_path,
            sep=';',
            index_col=0,
            parse_dates=['datetime']
        )
        if (historic_data_is_actual(df=df) or
                (to_datetime(getmtime(file_path) * 1000000000).date() ==
                 (_now() - timedelta(hours=1, minutes=45)).date())):
            df_historic_signals_sma = df
        else:
            df_historic_signals_sma = calc_historic_signals_sma(
                strategy_id=f'sma_{sma_periods.short}_{sma_periods.long}'
            )
    else:
        df_historic_signals_sma = calc_historic_signals_sma(
            strategy_id=f'sma_{sma_periods.short}_{sma_periods.long}'
        )


def update_data():
    """Функция вмещает в себя все функции выше.
    Задаёт условия, когда необходимо подгружать и рассчитывать исторические данные, а когда нет"""
    print('⏩START DATA CHECK. It can take 2 hours')

    download_shares()
    if not historic_data_is_actual(HistoricCandle):
        a = Share.get_figi_list()[:3]
        print(a)
        asyncio.run(download_historic_candles(figi_list=a))

    # for periods in sma_cross_periods_all:
    #     recalc_sma_if_inactual(sma_periods=periods)
    #     get_or_calc_sma_historic_signals(sma_periods=periods)

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
