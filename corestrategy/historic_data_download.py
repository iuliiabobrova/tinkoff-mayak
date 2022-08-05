# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции

from os.path import exists, getmtime
from typing import List
from threading import Event

from pandas import DataFrame, read_csv, to_datetime
from datetime import datetime, timedelta
from tinkoff.invest import Client, CandleInterval

from dtb.settings import INVEST_TOKEN
from corestrategy.hitoric_data_calc import calc_historic_signals_sma, calc_sma, save_historic_signals_rsi
from corestrategy.settings import *
from corestrategy.utils import historic_data_is_actual, _now, timer, retry_with_timeout, Limit
from tgbot.models import HistoricCandle, Share, MovingAverage


@retry_with_timeout(60)
def download_shares() -> None:
    """Позволяет получить из API список всех акций и их параметров"""

    with Client(INVEST_TOKEN) as client:
        for share in client.instruments.shares().instruments:
            Share.create(share=share)

    print('✅Downloaded list of shares')


@Limit(calls=5, period=1)
@retry_with_timeout(60)
def download_candles_by_figi(
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

    with Client(INVEST_TOKEN) as client:
        candles = client.get_all_candles(
            figi=figi,  # сюда должен поступать только один figi (id акции)
            from_=date_from,  # период времени определяется динамически
            to=date_to,
            interval=interval,  # запрашиваемая размерность свеч (дневная)
        )
        for candle in candles:
            HistoricCandle.create(candle=candle, figi=figi, interval='day')


def download_historic_candles(figi_list: List) -> None:
    """Позволяет загрузить исторические свечи из АПИ в БД"""

    max_days_available_by_api = 366

    print('⏩Downloading historic candles')
    for figi in figi_list:
        last_date = HistoricCandle.get_last_datetime_by_figi(figi=figi)
        if last_date is None:
            last_date = datetime(year=2012, month=1, day=1)
        days_have_passed = (_now() - last_date).days
        if days_have_passed == 0 or days_have_passed > max_days_available_by_api:  # проверка: не запрашиваем ли существующие в CSV данные
            continue

        await download_candles_by_figi(figi=figi, days=days_have_passed)

    print('✅Successfully downloaded and saved historic candles')


# проверка sma на актуальность
def get_or_calc_sma(df_close_prices: DataFrame,
                    figi_list: List,
                    sma_periods: SMACrossPeriods):
        if historic_data_is_actual(MovingAverage.objects.filter(name='date_time')):  # TODO ref
            pass
        else:
            calc_sma(
                df_close_prices=df_close_prices,
                figi_list=figi_list,
                sma_periods=sma_periods,
            )


# проверка sma-signals на актуальность
def get_or_calc_sma_historic_signals(df_close_prices: DataFrame,
                                     df_sma: DataFrame,
                                     df_shares: DataFrame,
                                     sma_periods: SMACrossPeriods) -> DataFrame:
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
                df_close_prices=df_close_prices,
                df_historic_sma=df_sma,
                df_shares=df_shares,
                csv_path=file_path,
                strategy_id=f'sma_{sma_periods.short}_{sma_periods.long}'
            )
    else:
        df_historic_signals_sma = calc_historic_signals_sma(
            df_close_prices=df_close_prices,
            df_historic_sma=df_sma,
            df_shares=df_shares,
            csv_path=file_path,
            strategy_id=f'sma_{sma_periods.short}_{sma_periods.long}'
        )

    return df_historic_signals_sma


def update_data() -> List:
    """Функция вмещает в себя все функции выше.
    Задаёт условия, когда необходимо подгружать и рассчитывать исторические данные, а когда нет"""
    print('⏩START DATA CHECK. It can take 2 hours')

    download_shares()
    if not historic_data_is_actual(Share):
        download_historic_candles(figi_list=Share.get_figi_list())

    df_sma_50_200 = get_or_calc_sma(
        df_close_prices=df_close_prices,
        figi_list=Share.get_figi_list(),
        sma_periods=sma_cross_periods_50_200
    )
    df_sma_30_90 = get_or_calc_sma(
        df_close_prices=df_close_prices,
        figi_list=Share.get_figi_list(),
        sma_periods=sma_cross_periods_30_90
    )
    df_sma_20_60 = get_or_calc_sma(
        df_close_prices=df_close_prices,
        figi_list=Share.get_figi_list(),
        sma_periods=sma_cross_periods_20_60
    )
    df_sma_list = [df_sma_50_200, df_sma_30_90, df_sma_20_60]

    df_historic_signals_sma_50_200 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_50_200,
        df_shares=Share.objects.all(),
        sma_periods=sma_cross_periods_50_200
    )
    df_historic_signals_sma_30_90 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_30_90,
        df_shares=Share.objects.all(),
        sma_periods=sma_cross_periods_30_90
    )
    df_historic_signals_sma_20_60 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_20_60,
        df_shares=Share.objects.all(),
        sma_periods=sma_cross_periods_20_60
    )
    df_historic_signals_sma_list = [
        df_historic_signals_sma_50_200,
        df_historic_signals_sma_30_90,
        df_historic_signals_sma_20_60
    ]

    # проверка rsi-signals на актуальность
    if exists(path='csv/historic_signals_rsi.csv'):
        df = read_csv(
            filepath_or_buffer='csv/historic_signals_rsi.csv',
            sep=';',
            index_col=0,
            parse_dates=['datetime'],
            low_memory=False
        )
        if historic_data_is_actual(df=df):
            df_historic_signals_rsi = df
            df_rsi = read_csv(
                filepath_or_buffer='csv/rsi.csv',
                sep=';',
                index_col=0
            )
        else:
            [df_historic_signals_rsi, df_rsi] = save_historic_signals_rsi(
                df_close_prices=df_close_prices,
                df_shares=df_shares
            )
    else:
        [df_historic_signals_rsi, df_rsi] = save_historic_signals_rsi(
            df_close_prices=df_close_prices,
            df_shares=df_shares
        )
    # calc_std(df_close_prices=df_close_prices) TODO (пока не используется)
    # calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)  TODO RSI-profit
    print('✅All data is actual')

    return [
            df_historic_signals_sma_list,
            df_historic_signals_rsi,
            df_sma_list,
            df_rsi
    ]
