# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции

from os.path import exists, getmtime
from typing import List
from time import perf_counter

from pandas import DataFrame, read_csv, to_datetime
from datetime import datetime, timedelta
from time import sleep
from tinkoff.invest import Client, CandleInterval

from dtb.settings import INVEST_TOKEN
from corestrategy.hitoric_data_calc import calc_historic_signals_sma, calc_sma, save_historic_signals_rsi
from corestrategy.settings import *
from corestrategy.utils import historic_data_is_actual, _now, convert_string_price_into_int_or_float


def get_shares_list_to_csv() -> List:
    """Позволяет получить из API список всех акций и их параметров"""

    try:
        with Client(INVEST_TOKEN) as client:  # обёртка
            # запрашивает название всех акций и закладывает их в переменную
            all_shares = client.instruments.shares()
        df_shares = DataFrame(data=all_shares.instruments)
        df_shares.set_index(keys=['figi'], inplace=True)
        figi_list = df_shares.index.tolist()
        df_shares.to_csv(path_or_buf='csv/shares.csv', sep=';')
        print('✅Downloaded list of shares')

    except Exception as e:
        print('No internet connection? Reconnecting in 60 sec:')
        print(e)
        sleep(60)
        [figi_list, df_shares] = get_shares_list_to_csv()

    return [figi_list, df_shares]


def last_data_parser(figi: str,
                     df_close_prices: DataFrame) -> datetime:
    """Позволяет получить самую позднюю дату из csv-файла c Historic_close_prices в формате datetime.
    используется в def one_figi_all_candles_request"""

    if exists('csv/historic_close_prices.csv'):  # проверка на существование файла
        try:
            # выделяем последнюю дату из df_close_prices
            figi_last_date = df_close_prices[figi].dropna().index.max()

        except KeyError:  # исключает случай, когда появляется новый figi
            figi_last_date = datetime(2012, 1, 1)

    else:
        figi_last_date = datetime(2012, 1, 1)

    return figi_last_date


def one_figi_all_candles_request(figi: str,
                                 days: int,
                                 df_fin_volumes: DataFrame,
                                 df_fin_close_prices: DataFrame) -> float:
    """Запрашивает все ОТСУТСТВУЮЩИЕ свечи по ОДНОМУ str(figi).
    Далее парсит полученные данные (цену закрытия, объёмы).
    Сохраняет данные в df."""

    try:
        def_start_time = perf_counter()

        now_date = _now()
        now_date = now_date - timedelta(
            hours=now_date.hour - 5,
            minutes=now_date.minute,
            seconds=now_date.second,
            microseconds=now_date.microsecond
        )
        date_from_ = now_date - timedelta(days=days) + timedelta(days=1)
        to_ = _now() + timedelta(days=1)

        with Client(INVEST_TOKEN) as client:
            for candle in client.get_all_candles(
                    figi=figi,  # сюда должен поступать только один figi (id акции)
                    # период времени определяется динамически функцией last_data_parser
                    from_=date_from_,
                    to=to_,
                    # запрашиваемая размерность японских свеч (дневная)
                    interval=CandleInterval.CANDLE_INTERVAL_DAY,
            ):
                # из ответа API парсит дату
                data = datetime(
                    year=candle.time.year,
                    month=candle.time.month,
                    day=candle.time.day
                )
                # из ответа API парсит цену закрытия
                if candle.close.nano == 0:
                    close_price = candle.close.units
                else:
                    close_price = round(candle.close.units + (candle.close.nano / 1_000_000_000), 6)
                volume = candle.volume  # из ответа API парсит объём торгов

                # если данных нет, записывает новые
                df_fin_close_prices.at[data, figi] = close_price
                # если данных нет, записывает новые
                df_fin_volumes.at[data, figi] = volume

        def_stop_time = perf_counter()
        time_on_def = def_stop_time - def_start_time

    except Exception as e:
        print(e)
        sleep(60)
        time_on_def = one_figi_all_candles_request(
            figi=figi,
            days=days,
            df_fin_volumes=df_fin_volumes,
            df_fin_close_prices=df_fin_close_prices
        )

    return time_on_def


def update_2_csv_with_historic_candles(df_fin_close_prices: DataFrame,
                                       df_fin_volumes: DataFrame.index,
                                       figi_list: List) -> List[DataFrame]:
    """Позволяет создать два CSV-файла с historic_close_prices и historic_volumes"""

    print('⏩Downloading historic candles')
    for figi in figi_list:
        last_date = last_data_parser(figi, df_fin_close_prices)
        days = (_now() - last_date).days
        # выше подготовка входных данных для функций

        if days != 0:  # проверка: не запрашиваем ли существующие в CSV данные
            time_on_def = one_figi_all_candles_request(figi=figi,
                                                       days=days,
                                                       df_fin_volumes=df_fin_volumes,
                                                       df_fin_close_prices=df_fin_close_prices)
            if days < 367:
                if time_on_def < 0.201:
                    sleep(0.201 - time_on_def)  # API позволяет делать не более 300 запросов в минуту
            elif time_on_def < 3:
                sleep(3 - time_on_def)

    df_fin_close_prices = df_fin_close_prices.sort_index()  # сортируем DF по датам по возрастанию
    df_fin_close_prices.to_csv(path_or_buf='csv/historic_close_prices.csv', sep=';')

    df_fin_volumes = df_fin_volumes.sort_index()  # сортируем DF по датам по возрастанию
    df_fin_volumes.to_csv(path_or_buf='csv/historic_volumes.csv', sep=';')
    print('✅Successfully downloaded and saved historic candles')

    return [df_fin_close_prices, df_fin_volumes]


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
            [df_close_prices, df_volumes] = update_2_csv_with_historic_candles(
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
