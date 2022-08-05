# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции

from os.path import exists, getmtime
from typing import List
from time import perf_counter
from threading import Event

from pandas import DataFrame, read_csv, to_datetime
from datetime import datetime, timedelta
from tinkoff.invest import Client, CandleInterval
from tinkoff.invest.utils import quotation_to_decimal

from dtb.settings import INVEST_TOKEN
from corestrategy.hitoric_data_calc import calc_historic_signals_sma, calc_sma, save_historic_signals_rsi
from corestrategy.settings import *
from corestrategy.utils import historic_data_is_actual, _now, Limit
from tgbot.models import HistoricCandle, Share


def download_shares() -> None:
    """Позволяет получить из API список всех акций и их параметров"""

    try:
        with Client(INVEST_TOKEN) as client:
            for share in client.instruments.shares():
                Share.create(share=share)

        print('✅Downloaded list of shares')

    except Exception as e:
        print('No internet connection? Reconnecting in 60 sec:')
        print(e)
        Event().wait(60)
        download_shares()


@Limit(calls=5, period=1)
def download_candles_by_figi(figi: str, days: int):
    """Запрашивает все ОТСУТСТВУЮЩИЕ свечи по ОДНОМУ str(figi)
    Сохраняет данные в df."""

    try:

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
                interval=CandleInterval.CANDLE_INTERVAL_DAY,  # запрашиваемая размерность свеч (дневная)
            )
            for candle in candles:
                HistoricCandle.create(candle=candle, figi=figi)



    except Exception as e:
        print(e)
        Event().wait(60)
        func_duration = download_candles_by_figi(figi=figi, days=days)

    return func_duration


def download_historic_candles(figi_list: List) -> None:
    """Позволяет загрузить исторические свечи из АПИ в БД"""

    max_days_available_by_api = 366

    print('⏩Downloading historic candles')
    for figi in figi_list:
        last_date = HistoricCandle.get_last_datetime_by_figi(figi=figi)
        if last_date is None:
            last_date = datetime(year=2012, month=1, day=1)
        days = (_now() - last_date).days

        if days == 0:  # проверка: не запрашиваем ли существующие в CSV данные
            continue

        if days <= max_days_available_by_api:
            await download_candles_by_figi(figi=figi, days=days)

    print('✅Successfully downloaded and saved historic candles')


# проверка sma на актуальность
def get_or_calc_sma(df_close_prices: DataFrame,
                    figi_list: List,
                    sma_periods: SMACrossPeriods) -> DataFrame:
    file_path = f'csv/sma_{sma_periods.short}_{sma_periods.long}.csv'
    if exists(path=file_path):
        df = read_csv(
            filepath_or_buffer=file_path,
            sep=';',
            index_col=0,
            parse_dates=[0]
        )
        if historic_data_is_actual(df=df):
            df_sma = df
        else:
            df_sma = calc_sma(
                df_close_prices=df_close_prices,
                figi_list=figi_list,
                sma_periods=sma_periods,
                csv_path=file_path
            )
    else:
        df_sma = calc_sma(
            df_close_prices=df_close_prices,
            figi_list=figi_list,
            sma_periods=sma_periods,
            csv_path=file_path
        )

    return df_sma


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

    [figi_list, df_shares] = get_shares_list_to_csv()

    print('⏩START DATA CHECK. It can take 2 hours')

    # проверка close_prices на актуальность
    if exists(path='csv/historic_close_prices.csv') and exists(path='csv/historic_volumes.csv'):
        df_close_prices = read_csv(
            filepath_or_buffer='csv/historic_close_prices.csv',
            sep=';',
            index_col=0,
            parse_dates=[0],
            dtype=float
        )

        if not historic_data_is_actual(df=df_close_prices):
            df_volumes = read_csv(
                filepath_or_buffer='csv/historic_volumes.csv',
                sep=';',
                index_col=0,
                parse_dates=[0],
                dtype=float
            )
            [df_close_prices, df_volumes] = download_historic_candles(
                df_fin_close_prices=df_close_prices,
                df_fin_volumes=df_volumes,
                figi_list=figi_list
            )
    else:
        if exists(path='csv/historic_close_prices.csv'):
            df_close_prices = read_csv(
                filepath_or_buffer='csv/historic_close_prices.csv',
                sep=';',
                index_col=0,
                parse_dates=[0],
                dtype=float
            )
        else:
            df_close_prices = DataFrame()  # пустой DF, если файла нет
        if exists(path='csv/historic_volumes.csv'):
            df_volumes = read_csv(
                filepath_or_buffer='csv/historic_volumes.csv',
                sep=';',
                index_col=0,
                parse_dates=[0],
                dtype=float
            )
        else:
            df_volumes = DataFrame()  # пустой DF, если файла нет
        [df_close_prices, df_volumes] = update_2_csv_with_historic_candles(
            df_fin_close_prices=df_close_prices,
            df_fin_volumes=df_volumes,
            figi_list=figi_list
        )

    df_sma_50_200 = get_or_calc_sma(
        df_close_prices=df_close_prices,
        figi_list=figi_list,
        sma_periods=sma_cross_periods_50_200
    )
    df_sma_30_90 = get_or_calc_sma(
        df_close_prices=df_close_prices,
        figi_list=figi_list,
        sma_periods=sma_cross_periods_30_90
    )
    df_sma_20_60 = get_or_calc_sma(
        df_close_prices=df_close_prices,
        figi_list=figi_list,
        sma_periods=sma_cross_periods_20_60
    )
    df_sma_list = [df_sma_50_200, df_sma_30_90, df_sma_20_60]

    df_historic_signals_sma_50_200 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_50_200,
        df_shares=df_shares,
        sma_periods=sma_cross_periods_50_200
    )
    df_historic_signals_sma_30_90 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_30_90,
        df_shares=df_shares,
        sma_periods=sma_cross_periods_30_90
    )
    df_historic_signals_sma_20_60 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_20_60,
        df_shares=df_shares,
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

    return [figi_list,
            df_shares,
            df_close_prices,
            df_historic_signals_sma_list,
            df_historic_signals_rsi,
            df_sma_list,
            df_rsi]
