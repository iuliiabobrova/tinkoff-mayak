# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции
# TODO вынести расчеты в отдельный модуль

from os.path import exists
from os import stat
from logging import exception, error

import pandas as pd
from numpy import nanpercentile
from pandas import DataFrame, to_datetime, read_csv, concat, merge
from datetime import datetime, timedelta, time
from tqdm import tqdm
from time import sleep
from threading import Event

from tinkoff.invest import Client, CandleInterval

from dtb.settings import INVEST_TOKEN
from corestrategy.settings import *
from corestrategy.utils import check_files_existing
from corestrategy.strategy_sma import columns_sma
from corestrategy.strategy_rsi import columns_rsi


def get_shares_list_to_csv() -> tuple[list, DataFrame]:
    """Позволяет получить из API список всех акций и их параметров"""

    global figi_list, df_shares

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
        get_shares_list_to_csv()

    return figi_list, df_shares


def last_data_parser(figi: str, df_close_prices: DataFrame) -> datetime:
    """Позволяет получить самую позднюю дату из csv-файла c Historic_close_prices в формате datetime.
    используется в def one_figi_all_candles_request"""

    if exists('csv/historic_close_prices.csv'):  # проверка на существование файла
        try:
            # выделяем последнюю дату из df_close_prices
            figi_last_date = df_close_prices[figi].dropna().index.max()

        except Exception as e:
            exception(e)
            figi_last_date = datetime(2012, 1, 1)

    else:
        figi_last_date = datetime(2012, 1, 1)

    return figi_last_date


def one_figi_all_candles_request(figi: str,
                                 days: int,
                                 df_fin_volumes: DataFrame,
                                 df_fin_close_prices: DataFrame) -> None:
    """Запрашивает все ОТСУТСТВУЮЩИЕ свечи по ОДНОМУ str(figi).
    Далее парсит полученные данные (цену закрытия, объёмы).
    Сохраняет данные в df.
    Вспомогательная функция для def create_2_csv_with_historic_candles"""

    with Client(INVEST_TOKEN) as client:
        for candle in client.get_all_candles(
                figi=figi,  # сюда должен поступать только один figi (id акции)
                # период времени определяется динамически функцией last_data_parser
                from_=datetime.utcnow() - timedelta(days=days),
                # запрашиваемая размерность японских свеч (дневная)
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            if candle.is_complete:
                # из ответа API парсит дату
                data = datetime(candle.time.year, candle.time.month, candle.time.day)
                # из ответа API парсит цену закрытия
                close_price = f'{candle.close.units}.{candle.close.nano // 10000000}'
                volume = candle.volume  # из ответа API парсит объём торгов

                # print('Цена открытия:', candle.open.units, '.', candle.open.nano // 10000000, sep='')
                # print('Цена закрытия:', candle.close.units, '.', candle.close.nano // 10000000, sep='')
                # print('Макс. цена:', candle.high.units, '.', candle.high.nano // 10000000, sep='')
                # print('Мин. цена:', candle.low.units, '.', candle.low.nano // 10000000, sep='')
                # print('Объём:', candle.volume, 'сделок')
                # print('')

                # если данных нет, записывает новые
                df_fin_close_prices.at[data, figi] = close_price
                # если данных нет, записывает новые
                df_fin_volumes.at[data, figi] = volume


def create_2_csv_with_historic_candles() -> tuple[DataFrame, DataFrame]:
    """Позволяет создать два CSV-файла с historic_close_prices и historic_volumes"""

    global figi_list

    # ниже подготовка DataFrame
    if exists('csv/historic_close_prices.csv'):  # проверка существует ли файл
        df_fin_close_prices = read_csv(filepath_or_buffer='csv/historic_close_prices.csv',
                                       sep=';',
                                       parse_dates=[0],
                                       index_col=0)
        df_fin_volumes = read_csv(filepath_or_buffer='csv/historic_volumes.csv',
                                  sep=';',
                                  parse_dates=[0],
                                  index_col=0)
    else:
        df_fin_close_prices = DataFrame()  # пустой DF, если файла нет
        df_fin_volumes = DataFrame()  # пустой DF, если файла нет

    for i in tqdm(range(len(figi_list)), desc='Downloading historic candles'):
        figi = figi_list[i]
        last_date = last_data_parser(figi, df_fin_close_prices)
        days = (datetime.utcnow() - last_date).days
        # выше подготовка входных данных для функций

        if days != 0:  # проверка: не запрашиваем ли существующие в CSV данные
            try:
                one_figi_all_candles_request(
                    figi, days, df_fin_volumes, df_fin_close_prices)
                if days > 3:
                    sleep(0.601)  # не более 100 запросов API в минуту
                else:
                    sleep(0.201)
            except Exception as e:
                print(e)
                print(f'Wait 60sec to download more candles, resource exhausted:')
                sleep(60)
                try:
                    one_figi_all_candles_request(
                        figi, days, df_fin_volumes, df_fin_close_prices)
                    if days > 3:
                        sleep(0.601)  # не более 100 запросов API в минуту
                    else:
                        sleep(0.201)
                except Exception as e:
                    error('Failed downloading candles twice', exc_info=e)

    df_fin_close_prices = df_fin_close_prices.sort_index()  # сортируем DF по датам по возрастанию
    df_fin_close_prices.to_csv(path_or_buf='csv/historic_close_prices.csv', sep=';')

    df_fin_volumes = df_fin_volumes.sort_index()  # сортируем DF по датам по возрастанию
    df_fin_volumes.to_csv(path_or_buf='csv/historic_volumes.csv', sep=';')
    print('✅Successfully downloaded and saved historic candles')

    return df_fin_close_prices, df_fin_volumes


def calc_std(df_close_prices: DataFrame) -> DataFrame:
    """Считает стандартное отклонение"""

    global figi_list

    df_price_std = DataFrame()  # пустой DF
    for figi in figi_list:
        sr_closes = df_close_prices[figi].dropna()  # получаем Series с close_prices для каждого figi
        std = sr_closes.tail(std_period).pct_change().std().round(3)  # считаем стандартное отклонение
        df_price_std.loc[figi, "std"] = std  # сохраняем стандартное отклонение в DF
    df_price_std.to_csv(path_or_buf='csv/std.csv', sep=';')
    print('✅Calc of STD done')

    return df_price_std


def calc_sma(df_close_prices: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Считает SMA"""

    global figi_list

    df_sma_final = DataFrame()  # пустой DF
    df_sma2 = DataFrame()  # пустой DF
    df_amount_of_sma = DataFrame(columns=['amount_of_sma_rows'])  # пустой DF

    for x in tqdm(range(len(figi_list)), desc='Calculating_historic_SMA'):
        figi = figi_list[x]
        df = df_close_prices[figi].dropna()  # получаем для каждого figi его Series с close_prices

        # скользящие средние за короткий период
        df_sma_short = df.rolling(period_of_short_sma - 1).mean().dropna().round(3)
        # скользящие средние за длинный период
        df_sma_long = df.rolling(period_of_long_sma - 1).mean().dropna().round(3)

        # объединяем короткие и длинные скользящие средние
        df_ma = concat([df_sma_short, df_sma_long], axis=1)
        # именуем столбцы корректно
        df_ma.columns = [f'{figi}.short', f'{figi}.long']
        # добавляем данные к итоговому DataFrame df_sma_final
        df_sma_final = merge(df_sma2,
                             df_ma,
                             left_index=True,
                             right_index=True,
                             how='outer')
        # сохраняем итоговый DF в переменную, чтобы можно было добавить данные следующим циклом
        df_sma2 = df_sma_final

        df_amount_of_sma.loc[figi] = [df_sma_long.size]

    df_amount_of_sma.to_csv(path_or_buf='csv/amount_sma.csv', sep=';')
    df_sma_final.sort_index()
    df_sma_final.to_csv(path_or_buf='csv/sma.csv', sep=';')
    print('✅Calc of SMA done')

    return df_amount_of_sma, df_sma_final


def historic_sma_cross(historic_short_sma: float,
                       historic_long_sma: float,
                       previous_historic_short_sma: float,
                       previous_historic_long_sma: float,
                       historic_last_price: float,
                       historic_date: datetime,
                       figi: str,
                       x: int) -> None:
    """Считает, пересекаются ли скользящие средние, а далее формирует сигнал, сохраняет его в DF"""

    global df_shares, df_historic_signals_sma

    crossing_buy = ((historic_short_sma > historic_long_sma) & (
            previous_historic_short_sma < previous_historic_long_sma) & (historic_last_price > historic_long_sma))
    crossing_sell = ((historic_short_sma < historic_long_sma) & (
            previous_historic_short_sma > previous_historic_long_sma) & (historic_last_price < historic_long_sma))

    # формирование сигнала, запись в DF
    if crossing_sell:
        buy_flag = 1
        sell_flag = 0
        profit = 0  # profit рассчитывается функцией calc_profit_sma() позже.
        ticker = df_shares.ticker[x]
        share_name = df_shares.name[x]
        currency = df_shares.currency[x]
        df_historic_signals_sma = concat(objs=[df_historic_signals_sma,
                                               (DataFrame(data=[[figi,
                                                                 ticker,
                                                                 share_name,
                                                                 historic_date,
                                                                 historic_last_price,
                                                                 sell_flag,
                                                                 buy_flag,
                                                                 'sma',
                                                                 profit,
                                                                 currency]], columns=columns_sma))],
                                         ignore_index=True)
    if crossing_buy:
        buy_flag = 0
        sell_flag = 1
        profit = 0  # profit рассчитывается функцией calc_profit_sma() позже
        ticker = df_shares.ticker[x]
        share_name = df_shares.name[x]
        currency = df_shares.currency[x]
        df_historic_signals_sma = concat(objs=[df_historic_signals_sma,
                                               (DataFrame(data=[[figi,
                                                                 ticker,
                                                                 share_name,
                                                                 historic_date,
                                                                 historic_last_price,
                                                                 sell_flag,
                                                                 buy_flag,
                                                                 'sma',
                                                                 profit,
                                                                 currency]], columns=columns_sma))],
                                         ignore_index=True)


def calc_one_historic_signal_sma(figi: str,
                                 x: int,
                                 amount_of_rows: int,
                                 df_fin_close_prices: DataFrame,
                                 df_all_historic_sma: DataFrame) -> None:
    """Подготавливает данные о [historic_last_price, historic_SMA, historic_date] для функции historic_sma_cross.
    По одному figi"""

    global df_shares, df_historic_signals_sma

    for index_of_row in range(-1, -amount_of_rows, -1):

        # подготовка DF с short_SMA по одному figi
        df_historic_short_sma = df_all_historic_sma[f'{figi}.short'].dropna()
        if df_historic_short_sma.size != 0:  # проверка на пустой DF
            historic_short_sma = df_historic_short_sma.loc[df_historic_short_sma.index[index_of_row]]
            # TODO TEST на тикере ABRD
            previous_historic_short_sma = df_historic_short_sma.loc[df_historic_short_sma.index[index_of_row - 1]]
            # TODO TEST на тикере ABRD
        else:
            historic_short_sma = None
            previous_historic_short_sma = None

        # подготовка DF с long_SMA по figi
        df_historic_long_sma = df_all_historic_sma[f'{figi}.long'].dropna()
        if df_historic_long_sma.size != 0:  # проверка на пустой DF
            historic_long_sma = df_historic_long_sma.loc[df_historic_long_sma.index[index_of_row]]
            # TODO TEST на тикере ABRD
            previous_historic_long_sma = df_historic_long_sma.loc[df_historic_long_sma.index[index_of_row - 1]]
            # TODO TEST на тикере ABRD
        else:
            historic_long_sma = None
            previous_historic_long_sma = None

        historic_last_price = df_fin_close_prices[figi][index_of_row + 1]
        historic_date = df_historic_long_sma.index[index_of_row]
        historic_sma_cross(historic_short_sma=historic_short_sma,
                           historic_long_sma=historic_long_sma,
                           previous_historic_short_sma=previous_historic_short_sma,
                           previous_historic_long_sma=previous_historic_long_sma,
                           historic_last_price=historic_last_price,
                           historic_date=historic_date,
                           figi=figi,
                           x=x)


def calc_historic_signals_sma(df_close_prices: DataFrame,
                              df_historic_sma: DataFrame,
                              df_amount_of_sma: DataFrame) -> DataFrame:
    """Подготовка данных для historic_sma_cross"""

    global figi_list, df_shares, df_historic_signals_sma
    # Подготовка DF
    df_historic_signals_sma = DataFrame(columns=columns_sma)

    for x in tqdm(range(len(figi_list)), desc='Calculating_historic_signals_sma'):
        figi = df_historic_sma.columns[::2][x][:12]
        amount_of_rows = int(df_amount_of_sma.amount_of_sma_rows[figi])
        calc_one_historic_signal_sma(figi=figi,
                                     df_fin_close_prices=df_close_prices,
                                     df_all_historic_sma=df_historic_sma,
                                     amount_of_rows=amount_of_rows,
                                     x=x)

    df_historic_signals_sma.sort_values(by='datetime', inplace=True)
    df_historic_signals_sma.reset_index(drop=True, inplace=True)
    df_historic_signals_sma.to_csv(path_or_buf='csv/historic_signals_sma.csv', sep=';')
    print('✅Historic_signals_SMA_are_saved')

    return df_historic_signals_sma


def calc_historic_signals_rsi(df_close_prices: DataFrame) -> DataFrame:
    """Функция позволяет рассчитать индикатор RSI и сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    global figi_list, df_shares

    df_historic_signals_rsi = DataFrame(columns=columns_rsi)  # пустой DF

    # расчет по формуле RSI
    delta = df_close_prices.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period_of_ema, adjust=False).mean()
    ema_down = down.ewm(com=period_of_ema, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = (100 - (100 / (1 + rs))).round(2)
    rsi.to_csv(path_or_buf='csv/historic_rsi_data.csv', sep=';')

    for x in tqdm(range(len(figi_list)), desc='Calculating_historic_rsi_signals'):
        figi = figi_list[x]
        # верхняя граница RSI, значение 95 отсеивает RSI примерно выше 70
        upper_rsi = nanpercentile(rsi[figi], upper_rsi_percentile)
        # нижняя граница RSI, значение 2.5 отсеивает RSI примерно ниже 30
        lower_rsi = nanpercentile(rsi[figi], lower_rsi_percentile)
        # цикл проверки DF rsi на условие upper_rsi, lower_rsi
        for y in range(len(rsi[figi])):
            rsi_float = rsi[figi][y]
            historic_date_rsi = rsi.index[y]
            historic_last_price_rsi = df_close_prices[figi][historic_date_rsi]

            if rsi_float >= upper_rsi:  # если истина, записываем в DF сигнал на продажу
                ticker = df_shares.ticker[figi]
                share_name = df_shares.name[figi]
                currency = df_shares.currency[figi]
                sell_flag = 1
                buy_flag = 0
                profit = 0  # profit рассчитывается позже в def calc_profit
                df_historic_signals_rsi = concat(objs=[df_historic_signals_rsi,
                                                       (DataFrame(data=[[figi,
                                                                         ticker,
                                                                         share_name,
                                                                         historic_date_rsi,
                                                                         historic_last_price_rsi,
                                                                         rsi_float,
                                                                         sell_flag,
                                                                         buy_flag,
                                                                         'rsi',
                                                                         profit,
                                                                         currency]], columns=columns_rsi))],
                                                 ignore_index=True)

            if rsi_float <= lower_rsi:  # если истина, записываем в DF сигнал на покупку
                ticker = df_shares.ticker[figi]
                share_name = df_shares.name[figi]
                currency = df_shares.currency[figi]
                sell_flag = 0
                buy_flag = 1
                profit = 0  # profit рассчитывается позже в def calc_profit
                df_historic_signals_rsi = concat(objs=[df_historic_signals_rsi,
                                                       (DataFrame(data=[[figi,
                                                                         ticker,
                                                                         share_name,
                                                                         historic_date_rsi,
                                                                         historic_last_price_rsi,
                                                                         rsi_float,
                                                                         sell_flag,
                                                                         buy_flag,
                                                                         'rsi',
                                                                         profit,
                                                                         currency]], columns=columns_rsi))],
                                                 ignore_index=True)

    # Сортировка по дате. В конце самые актуальные сигналы
    df_historic_signals_rsi.sort_values(by='datetime', inplace=True)
    df_historic_signals_rsi.reset_index(drop=True, inplace=True)
    df_historic_signals_rsi.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

    return df_historic_signals_rsi


def calc_profit(df_historic_signals_rsi: DataFrame) -> None:
    """Считает доходность от использования двух последних сигналов SMA и RSI"""

    global figi_list, df_historic_signals_sma

    df_profit_sma = DataFrame(columns=['profit'])
    df_profit_rsi = DataFrame(columns=['profit'])
    profit = 'error'

    for x in tqdm(range(len(figi_list)), desc='Calc_profit_of_sma_signals'):
        try:
            figi = figi_list[x]
            if (df_historic_signals_sma.loc[figi].tail(2).sell_flag[0]) == 0 \
                    and (df_historic_signals_sma.loc[figi].tail(2).buy_flag[0] == 1):
                profit = (100 * (df_historic_signals_sma.loc[figi[:12]].tail(2).last_price.pct_change()[1])).round(2)
            if (df_historic_signals_sma.loc[figi].tail(2).sell_flag[0]) == 1 \
                    and (df_historic_signals_sma.loc[figi].tail(2).buy_flag[0] == 0):
                profit = -(100 * (df_historic_signals_sma.loc[figi[:12]].tail(2).last_price.pct_change()[1])).round(2)
            df_profit_sma.loc[figi] = profit
        except:
            # TODO заменить try-except на if (когда нет сигналов по бумаге)
            pass

    for x in tqdm(range(len(figi_list)), desc='Calc_profit_of_rsi_signals'):
        try:
            figi = figi_list[x]
            if (df_historic_signals_rsi.loc[figi].tail(2).sell_flag[0]) == 0 and (
                    df_historic_signals_rsi.loc[figi].tail(2).buy_flag[0] == 1):
                profit = (100 * (df_historic_signals_rsi.loc[figi[:12]].tail(2).last_price.pct_change()[1])).round(2)
            if (df_historic_signals_rsi.loc[figi].tail(2).sell_flag[0]) == 1 and (
                    df_historic_signals_rsi.loc[figi].tail(2).buy_flag[0] == 0):
                profit = -(100 * (df_historic_signals_rsi.loc[figi[:12]].tail(2).last_price.pct_change()[1])).round(2)
            df_profit_rsi.loc[figi] = profit
        except:
            # TODO заменить try-except на if (когда нет сигналов по бумаге)
            pass

    df_profit_sma.to_csv(path_or_buf='csv/historic_profit_sma.csv', sep=';')
    df_profit_rsi.to_csv(path_or_buf='csv/historic_profit_rsi.csv', sep=';')
    print('✅Calculation_of_profit_is_done')


def run_download_data() -> None:
    """Функция вмещает в себя все функции выше.
    Задаёт условия, когда необходимо подгружать исторические данные, а когда нет"""

    global figi_list, df_shares, df_historic_signals_sma, data_downloading_flag

    figi_list, df_shares = get_shares_list_to_csv()

    if not check_files_existing():
        data_downloading_flag = True
        print('❌No files. It will be fixed automatically')
        print('⏩START DATA DOWNLOADING. It can take 30 min')

        # проверка historic_close_prices на актуальность
        if exists(path='csv/historic_close_prices.csv') and exists(path='csv/historic_volumes.csv'):
            df = pd.read_csv(filepath_or_buffer='csv/historic_close_prices.csv',
                             sep=';',
                             index_col=0,
                             parse_dates=[0])
            if df.index.max().date() + timedelta(days=1) == datetime.now().date():
                df_close_prices = df
            else:
                df_close_prices, df_volumes = create_2_csv_with_historic_candles()
        else:
            df_close_prices, df_volumes = create_2_csv_with_historic_candles()

        # проверка sma на актуальность
        if exists(path='csv/sma.csv'):
            df = pd.read_csv(filepath_or_buffer='csv/sma.csv',
                             sep=';',
                             index_col=0,
                             parse_dates=[0])
            if df.index.max().date() + timedelta(days=1) == datetime.now().date():
                df_sma = df
                df_amount_of_sma = pd.read_csv(filepath_or_buffer='csv/amount_sma.csv',
                                               sep=';',
                                               index_col=0)
            else:
                df_amount_of_sma, df_sma = calc_sma(df_close_prices=df_close_prices)
        else:
            df_amount_of_sma, df_sma = calc_sma(df_close_prices=df_close_prices)

        if exists(path='csv/historic_signals_sma.csv'):
            df = pd.read_csv(filepath_or_buffer='csv/historic_signals_sma.csv',
                             sep=';',
                             index_col=0,
                             parse_dates=['datetime'])
            if df.datetime.max().date() + timedelta(days=1) == datetime.now().date():
                df_historic_signals_sma = df
            else:
                df_historic_signals_sma = calc_historic_signals_sma(df_close_prices=df_close_prices,
                                                                    df_historic_sma=df_sma,
                                                                    df_amount_of_sma=df_amount_of_sma)
        else:
            df_historic_signals_sma = calc_historic_signals_sma(df_close_prices=df_close_prices,
                                                                df_historic_sma=df_sma,
                                                                df_amount_of_sma=df_amount_of_sma)

        if exists(path='csv/historic_signals_rsi.csv'):
            df = pd.read_csv(filepath_or_buffer='csv/historic_signals_rsi.csv',
                             sep=';',
                             index_col=0,
                             parse_dates=['datetime'])
            if df.datetime.max().date() + timedelta(days=1) == datetime.now().date():
                df_historic_signals_rsi = df
            else:
                df_historic_signals_rsi = calc_historic_signals_rsi(df_close_prices=df_close_prices)
        else:
            df_historic_signals_rsi = calc_historic_signals_rsi(df_close_prices=df_close_prices)

        # calc_std(df_close_prices=df_close_prices) # TODO
        calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)  # TODO RSI-profit
        print('✅All data saving complete')
        data_downloading_flag = False
    else:
        # подготовка DF
        df_close_prices = read_csv(filepath_or_buffer='csv/historic_close_prices.csv',
                                   sep=';',
                                   parse_dates=[0],
                                   index_col=0)
        df_historic_signals_sma = read_csv(filepath_or_buffer='csv/historic_signals_sma.csv',
                                           sep=';',
                                           index_col=0)
        df_historic_signals_rsi = read_csv(filepath_or_buffer='csv/historic_signals_rsi.csv',
                                           sep=';',
                                           index_col=0)

    while True:
        mod_date = datetime.now() - to_datetime(stat('csv/sma.csv').st_mtime_ns)
        if (time(hour=3) < datetime.now().time() < time(hour=6) and mod_date > timedelta(hours=3)) or \
                (mod_date > timedelta(hours=24)):
            data_downloading_flag = True
            print('❌Data is outdated')
            print('⏩START DATA DOWNLOADING. It can take 30 min')
            create_2_csv_with_historic_candles()

            # расчет исторических индикаторов
            # calc_std(df_close_prices=df_close_prices) TODO (пока не используется)
            calc_sma(df_close_prices=df_close_prices)

            # подсчет исторических доходностей на основе сигналов
            calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)
            print('✅All data saving complete')
            data_downloading_flag = False

        else:
            Event().wait(3600)


data_downloading_flag = False
