# Код написан на основе документации API https://tinkoff.github.io/investAPI/
# В основном используется Сервис Котировок https://tinkoff.github.io/investAPI/marketdata/
# Figi - это уникальный ID акции
# TODO вынести расчеты в отдельный модуль

from os.path import exists, getmtime
from typing import List
from time import perf_counter

from numpy import nanpercentile
from pandas import DataFrame, read_csv, concat, merge, isna, to_datetime
from datetime import datetime, timedelta
from tqdm import tqdm
from time import sleep
from tinkoff.invest import Client, CandleInterval

from dtb.settings import INVEST_TOKEN
from corestrategy.settings import *
from corestrategy.utils import save_signal_to_df, historic_data_is_actual, _now, convert_stringprice_into_int_or_float


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
        now_date = now_date - timedelta(hours=now_date.hour - 5,
                                        minutes=now_date.minute,
                                        seconds=now_date.second,
                                        microseconds=now_date.microsecond)
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
                data = datetime(year=candle.time.year,
                                month=candle.time.month,
                                day=candle.time.day)
                # из ответа API парсит цену закрытия
                close_price = f'{candle.close.units}.{candle.close.nano}'
                close_price = convert_stringprice_into_int_or_float(price=close_price)
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
        time_on_def = one_figi_all_candles_request(figi=figi,
                                                   days=days,
                                                   df_fin_volumes=df_fin_volumes,
                                                   df_fin_close_prices=df_fin_close_prices)

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


def calc_std(df_close_prices: DataFrame,
             figi_list: List) -> DataFrame:
    """Считает стандартное отклонение"""

    df_price_std = DataFrame()  # пустой DF
    for figi in figi_list:
        sr_closes = df_close_prices[figi].dropna()  # получаем Series с close_prices для каждого figi
        std = sr_closes.tail(std_period).pct_change().std().round(3)  # считаем стандартное отклонение
        df_price_std.loc[figi, "std"] = std  # сохраняем стандартное отклонение в DF
    df_price_std.to_csv(path_or_buf='csv/std.csv', sep=';')
    print('✅Calc of STD done')

    return df_price_std


def calc_sma(df_close_prices: DataFrame,
             figi_list: List,
             sma_periods: SMACrossPeriods,
             csv_path: str) -> DataFrame:
    """Считает SMA"""

    df_sma_final = DataFrame()  # пустой DF
    df_sma2 = DataFrame()  # пустой DF

    print('⏩Start calculating SMA-float')
    for figi in figi_list:
        try:
            df = df_close_prices[figi].dropna()  # получаем для каждого figi его Series с close_prices

            # скользящие средние за короткий период
            df_sma_short = df.rolling(sma_periods.short - 1).mean().dropna().round(3)
            # скользящие средние за длинный период
            df_sma_long = df.rolling(sma_periods.long - 1).mean().dropna().round(3)

            # объединяем короткие и длинные скользящие средние
            df_ma = concat([df_sma_short, df_sma_long], axis=1, copy=False)
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

        except KeyError:
            print('No data to calc. Figi:', figi)

    df_sma_final.sort_index()
    df_sma_final.to_csv(path_or_buf=csv_path, sep=';')
    print('✅Calc of SMA done')

    return df_sma_final


def historic_sma_cross(historic_short_sma: float,
                       historic_long_sma: float,
                       previous_historic_short_sma: float,
                       previous_historic_long_sma: float,
                       historic_last_price: float,
                       historic_date: datetime,
                       figi: str,
                       df_shares: DataFrame,
                       df_historic_signals_sma: DataFrame) -> DataFrame:
    """Считает, пересекаются ли скользящие средние, а далее формирует сигнал, сохраняет его в DF"""

    crossing_buy = ((historic_short_sma > historic_long_sma) & (
            previous_historic_short_sma < previous_historic_long_sma) & (historic_last_price > historic_long_sma))
    crossing_sell = ((historic_short_sma < historic_long_sma) & (
            previous_historic_short_sma > previous_historic_long_sma) & (historic_last_price < historic_long_sma))

    # формирование сигнала, запись в DF
    if crossing_sell:
        df_historic_signals_sma = save_signal_to_df(buy_flag=0, sell_flag=1, last_price=historic_last_price, figi=figi,
                                                    date=historic_date, strategy='sma', df_shares=df_shares,
                                                    df=df_historic_signals_sma)
    if crossing_buy:
        df_historic_signals_sma = save_signal_to_df(buy_flag=1, sell_flag=0, last_price=historic_last_price, figi=figi,
                                                    date=historic_date, strategy='sma', df_shares=df_shares,
                                                    df=df_historic_signals_sma)

    return df_historic_signals_sma


def calc_historic_signals_sma_by_figi(figi: str,
                                      amount_of_rows: int,
                                      df_fin_close_prices: DataFrame,
                                      df_all_historic_sma: DataFrame,
                                      df_shares: DataFrame,
                                      df_historic_signals_sma: DataFrame) -> DataFrame:
    """Подготавливает данные о [historic_last_price, historic_SMA, historic_date] для функции historic_sma_cross.
    По одному figi"""

    if amount_of_rows >= 20:
        amount_of_rows = 20

    for index_of_row in range(-1, -amount_of_rows, -1):

        # подготовка DF с short_SMA и long_SMA по одному figi
        sr_short_sma = df_all_historic_sma[f'{figi}.short'].dropna()
        sr_long_sma = df_all_historic_sma[f'{figi}.long'].dropna()
        if sr_short_sma.size != 0 and sr_long_sma.size != 0:  # проверка на пустой DF
            historic_short_sma = float(sr_short_sma.loc[sr_short_sma.index[index_of_row]])
            previous_historic_short_sma = float(sr_short_sma.loc[sr_short_sma.index[index_of_row - 1]])
            historic_long_sma = float(sr_long_sma.loc[sr_long_sma.index[index_of_row]])
            previous_historic_long_sma = float(sr_long_sma.loc[sr_long_sma.index[index_of_row - 1]])

            historic_last_price = float(df_fin_close_prices[figi][index_of_row + 1])
            if historic_last_price != 0:
                historic_date = sr_long_sma.index[index_of_row]
                df_historic_signals_sma = historic_sma_cross(historic_short_sma=historic_short_sma,
                                                             historic_long_sma=historic_long_sma,
                                                             previous_historic_short_sma=previous_historic_short_sma,
                                                             previous_historic_long_sma=previous_historic_long_sma,
                                                             historic_last_price=historic_last_price,
                                                             historic_date=historic_date,
                                                             figi=figi,
                                                             df_shares=df_shares,
                                                             df_historic_signals_sma=df_historic_signals_sma)
    return df_historic_signals_sma


def calc_historic_signals_sma(df_close_prices: DataFrame,
                              df_historic_sma: DataFrame,
                              df_shares: DataFrame,
                              csv_path: str) -> DataFrame:
    """Подготовка данных для historic_sma_cross"""

    # Подготовка DF
    df_historic_signals_sma = DataFrame(columns=columns_sma)

    print('⏩Historic signals SMA calc starts')
    for figi in df_historic_sma.columns[::2]:
        figi = figi[:12]
        amount_of_rows = df_historic_sma[f'{figi}.long'].dropna().shape[0]
        df_historic_signals_sma = calc_historic_signals_sma_by_figi(
            figi=figi,
            df_fin_close_prices=df_close_prices,
            df_all_historic_sma=df_historic_sma,
            amount_of_rows=amount_of_rows,
            df_shares=df_shares,
            df_historic_signals_sma=df_historic_signals_sma
        )

    df_historic_signals_sma.sort_values(by='datetime', inplace=True)
    df_historic_signals_sma.reset_index(drop=True, inplace=True)
    df_historic_signals_sma.to_csv(path_or_buf=csv_path, sep=';')
    print('✅Historic_signals_SMA_are_saved')

    return df_historic_signals_sma


def calc_one_figi_signals_rsi(rsi: DataFrame,
                              figi: str,
                              upper_rsi: float,
                              lower_rsi: float,
                              df_close_prices: DataFrame,
                              df_shares: DataFrame) -> DataFrame:
    df = DataFrame(columns=columns_rsi)
    count = len(rsi[figi])
    if count >= 20:
        count = 20

    for y in range(count):
        rsi_float = rsi[figi][y]
        historic_date_rsi = rsi.index[y]
        historic_last_price_rsi = df_close_prices[figi][historic_date_rsi]

        if isna(historic_last_price_rsi):  # если close_price пустая, берёт данные за последние 4 дня
            for f in range(1, 5):
                historic_date_rsi_2 = rsi.index[y - f]
                historic_last_price_rsi = df_close_prices[figi][historic_date_rsi_2]

        if rsi_float >= upper_rsi:  # если истина, записываем в DF сигнал на продажу
            df = save_signal_to_df(buy_flag=0, sell_flag=1, last_price=historic_last_price_rsi, figi=figi,
                                   date=historic_date_rsi, strategy='rsi', df_shares=df_shares, df=df,
                                   rsi_float=rsi_float)

        if rsi_float <= lower_rsi:  # если истина, записываем в DF сигнал на покупку

            df = save_signal_to_df(buy_flag=1, sell_flag=0, last_price=historic_last_price_rsi, figi=figi,
                                   date=historic_date_rsi, strategy='rsi', df_shares=df_shares, df=df,
                                   rsi_float=rsi_float)

    return df


def calc_historic_signals_rsi(df_close_prices: DataFrame,
                              df_shares: DataFrame) -> DataFrame:
    """Функция позволяет рассчитать индикатор RSI и сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    # расчет по формуле RSI
    delta = df_close_prices.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period_of_ema, adjust=False).mean()
    ema_down = down.ewm(com=period_of_ema, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = (100 - (100 / (1 + rs))).round(2)

    print('⏩Historic signals RSI calc starts')
    for figi in df_close_prices.columns:
        # верхняя граница RSI, значение 95 отсеивает RSI примерно выше 70
        upper_rsi = nanpercentile(rsi[figi], upper_rsi_percentile)
        # нижняя граница RSI, значение 2.5 отсеивает RSI примерно ниже 30
        lower_rsi = nanpercentile(rsi[figi], lower_rsi_percentile)

        df_historic_signals_rsi = calc_one_figi_signals_rsi(rsi=rsi,
                                                            figi=figi,
                                                            upper_rsi=upper_rsi,
                                                            lower_rsi=lower_rsi,
                                                            df_close_prices=df_close_prices,
                                                            df_shares=df_shares)

        yield df_historic_signals_rsi


def save_historic_signals_rsi(df_close_prices: DataFrame,
                              df_shares: DataFrame) -> DataFrame:
    """Обеспечивает сохранение сигналов в DataFrame и CSV"""

    list_df = calc_historic_signals_rsi(df_close_prices=df_close_prices,
                                        df_shares=df_shares)
    df_historic_signals_rsi = concat(objs=list_df, ignore_index=True, copy=False)

    # Сортировка по дате. В конце самые актуальные сигналы
    df_historic_signals_rsi.sort_values(by='datetime', inplace=True)
    df_historic_signals_rsi.reset_index(drop=True, inplace=True)
    df_historic_signals_rsi.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')
    print('✅Historic signals RSI are saved')

    return df_historic_signals_rsi


def calc_profit(df_historic_signals_rsi: DataFrame,
                figi_list: List,
                df_historic_signals_sma: DataFrame) -> None:
    """Считает доходность от использования двух последних сигналов SMA и RSI"""

    df_profit_sma = DataFrame(columns=['profit'])
    df_profit_rsi = DataFrame(columns=['profit'])
    profit = 'error'

    for x in tqdm(range(len(figi_list)), desc='Calc_profit_of_sma_signals'):  # TODO убрать tqdm
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

    for x in tqdm(range(len(figi_list)), desc='Calc_profit_of_rsi_signals'):  # TODO убрать tqdm
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


def update_data() -> List:
    """Функция вмещает в себя все функции выше.
    Задаёт условия, когда необходимо подгружать и рассчитывать исторические данные, а когда нет"""

    [figi_list, df_shares] = get_shares_list_to_csv()

    print('⏩START DATA CHECK. It can take 2 hours')

    # проверка close_prices на актуальность
    if exists(path='csv/historic_close_prices.csv') and exists(path='csv/historic_volumes.csv'):
        df_close_prices = read_csv(filepath_or_buffer='csv/historic_close_prices.csv',
                                   sep=';',
                                   index_col=0,
                                   parse_dates=[0],
                                   dtype=float)

        if not historic_data_is_actual(df=df_close_prices):
            df_volumes = read_csv(filepath_or_buffer='csv/historic_volumes.csv',
                                  sep=';',
                                  index_col=0,
                                  parse_dates=[0],
                                  dtype=float)
            [df_close_prices, df_volumes] = update_2_csv_with_historic_candles(df_fin_close_prices=df_close_prices,
                                                                               df_fin_volumes=df_volumes,
                                                                               figi_list=figi_list)
    else:
        if exists(path='csv/historic_close_prices.csv'):
            df_close_prices = read_csv(filepath_or_buffer='csv/historic_close_prices.csv',
                                       sep=';',
                                       index_col=0,
                                       parse_dates=[0],
                                       dtype=float)
        else:
            df_close_prices = DataFrame()  # пустой DF, если файла нет
        if exists(path='csv/historic_volumes.csv'):
            df_volumes = read_csv(filepath_or_buffer='csv/historic_volumes.csv',
                                  sep=';',
                                  index_col=0,
                                  parse_dates=[0],
                                  dtype=float)
        else:
            df_volumes = DataFrame()  # пустой DF, если файла нет
        [df_close_prices, df_volumes] = update_2_csv_with_historic_candles(df_fin_close_prices=df_close_prices,
                                                                           df_fin_volumes=df_volumes,
                                                                           figi_list=figi_list)

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
        figi_list=figi_list,
        df_shares=df_shares,
        sma_periods=sma_cross_periods_50_200
    )
    df_historic_signals_sma_30_90 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_30_90,
        figi_list=figi_list,
        df_shares=df_shares,
        sma_periods=sma_cross_periods_30_90
    )
    df_historic_signals_sma_20_60 = get_or_calc_sma_historic_signals(
        df_close_prices=df_close_prices,
        df_sma=df_sma_20_60,
        figi_list=figi_list,
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
        df = read_csv(filepath_or_buffer='csv/historic_signals_rsi.csv',
                      sep=';',
                      index_col=0,
                      parse_dates=['datetime'],
                      low_memory=False)
        if historic_data_is_actual(df=df):
            df_historic_signals_rsi = df
        else:
            df_historic_signals_rsi = save_historic_signals_rsi(df_close_prices=df_close_prices,
                                                                df_shares=df_shares)
    else:
        df_historic_signals_rsi = save_historic_signals_rsi(df_close_prices=df_close_prices,
                                                            df_shares=df_shares)
    # calc_std(df_close_prices=df_close_prices) TODO (пока не используется)
    # calc_profit(df_historic_signals_rsi=df_historic_signals_rsi)  TODO RSI-profit
    print('✅All data is actual')

    return [figi_list, df_shares, df_close_prices, df_historic_signals_sma_list, df_historic_signals_rsi, df_sma_list]


# проверка sma на актуальность
def get_or_calc_sma(df_close_prices: DataFrame,
                    figi_list: List,
                    sma_periods: SMACrossPeriods) -> DataFrame:
    file_path = f'csv/sma_{sma_periods.short}_{sma_periods.long}.csv'
    if exists(path=file_path):
        df = read_csv(filepath_or_buffer=file_path,
                      sep=';',
                      index_col=0,
                      parse_dates=[0])
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
                                     figi_list: List,
                                     df_shares: DataFrame,
                                     sma_periods: SMACrossPeriods) -> DataFrame:
    file_path = f'csv/historic_signals_sma_{sma_periods.short}_{sma_periods.long}.csv'
    if exists(path=file_path):
        df = read_csv(filepath_or_buffer=file_path,
                      sep=';',
                      index_col=0,
                      parse_dates=['datetime'])
        if (historic_data_is_actual(df=df) or
                (to_datetime(getmtime(file_path) * 1000000000).date() ==
                 (_now() - timedelta(hours=1, minutes=45)).date())):
            df_historic_signals_sma = df
        else:
            df_historic_signals_sma = calc_historic_signals_sma(
                df_close_prices=df_close_prices,
                df_historic_sma=df_sma,
                df_shares=df_shares,
                csv_path=file_path
            )
    else:
        df_historic_signals_sma = calc_historic_signals_sma(
            df_close_prices=df_close_prices,
            df_historic_sma=df_sma,
            df_shares=df_shares,
            csv_path=file_path
        )

    return df_historic_signals_sma
