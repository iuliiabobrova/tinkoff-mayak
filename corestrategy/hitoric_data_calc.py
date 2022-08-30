from decimal import Decimal
from typing import List
from datetime import datetime
from numpy import nanpercentile

from pandas import DataFrame, Series, concat, isna
from toolz import unique

from corestrategy.settings import (
    std_period, SMACrossPeriods,
    columns_rsi, period_of_ema, lower_rsi_percentile,
    upper_rsi_percentile, sma_cross_periods_all
)
from corestrategy.utils import save_signal_to_df
from corestrategy.historic_data_download import get_figi_list_with_inactual_historic_data
from tgbot.models import HistoricCandle, MovingAverage, StandardDeviation

from django.db.models import Avg, F, RowRange, Window


def calc_std_deviation(figi_list: List[str]):
    """Считает стандартное отклонение"""
    for figi in figi_list:
        candles = HistoricCandle.get_candles_by_figi(figi=figi)
        if len(candles) < std_period:
            continue
        close_prices_series = Series(list(map(lambda candle: [candle.close_price], candles)))
        std_deviation = close_prices_series.tail(std_period).pct_change().std().round(3)
        StandardDeviation.create(value=std_deviation, figi=figi, period=std_period)
    print('✅Calc of standard deviation done')


def calc_sma(period: int, figi_list: List[str]):
    """Считает SMA"""

    for figi in figi_list:
        candles = HistoricCandle.get_candles_by_figi(figi=figi)
        if len(candles) < period:
            continue
        close_prices_list = list(map(lambda candle: [candle.close_price], candles))
        datetime_list = list(map(lambda candle: candle.date_time, candles))
        df_historic_prices = DataFrame(index=datetime_list, data=close_prices_list, columns=['close_price'])
        df_sma = df_historic_prices.rolling(period - 1).mean().dropna().round(3)
        for index in df_sma.index:
            MovingAverage.create(
                value=df_sma.close_price[index],
                figi=figi,
                period=period - 1,
                date_time=index
            )


# todo ТЕСТОВАЯ ФУНКЦИЯ
def calc_sma_new(period: int, figi_list: List[str]):
    for figi in figi_list:
        items = HistoricCandle.objects.filter(figi=figi).annotate(
            avg=Window(
                expression=Avg('value'),
                order_by=F('date_time').asc(),
                frame=RowRange(start=-period, end=0)
            )
        )
        print(items)

# проверка sma на актуальность
def recalc_sma_if_inactual():
    print('⏩Start calculating SMA-float')
    period_tuples = map(lambda periods: (periods.short, periods.long), sma_cross_periods_all)
    for period in list(sum(period_tuples, ())):
        figi_list = get_figi_list_with_inactual_historic_data(MovingAverage, period=period)
        calc_sma(period=period, figi_list=figi_list)
    print('✅Calc of SMA done')


def historic_sma_cross(previous_historic_short_sma: float,
                       previous_historic_long_sma: float,
                       historic_last_price: float,
                       historic_date: datetime,
                       figi: str,
                       strategy_id: str) -> DataFrame:
    """Считает, пересекаются ли скользящие средние, а далее формирует сигнал, сохраняет его в DF"""

    crossing_buy = ((historic_short_sma > historic_long_sma) & (
            previous_historic_short_sma < previous_historic_long_sma) & (historic_last_price > historic_long_sma))
    crossing_sell = ((historic_short_sma < historic_long_sma) & (
            previous_historic_short_sma > previous_historic_long_sma) & (historic_last_price < historic_long_sma))

    # формирование сигнала, запись в DF
    if crossing_sell or crossing_buy:
        buy_flag = 0 if crossing_sell else 1
        [df_historic_signals_sma, hist_signal] = save_signal_to_df(buy_flag=buy_flag, last_price=historic_last_price,
                                                                   figi=figi, date_time=historic_date,
                                                                   strategy_id=strategy_id)


def calc_historic_signals_sma_by_figi(strategy_id: str):
    """Подготавливает данные о [historic_last_price, historic_SMA, historic_date] для функции historic_sma_cross.
    По одному figi"""

    print(f'⏩Historic signals {strategy_id} calc starts')
    figi_list = list(unique(candles_generator, key=lambda candle: candle.time))  # TODO заменить generator на список объектов MA
    for figi in figi_list:
        amount_of_rows = df_historic_sma[f'{figi}.long'].dropna().shape[0]

        if amount_of_rows >= 20:  # ограничиваем окно подсчета сигналов 20-тью днями
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
                    df_historic_signals_sma = historic_sma_cross(
                        previous_historic_short_sma=previous_historic_short_sma,
                        previous_historic_long_sma=previous_historic_long_sma,
                        historic_last_price=historic_last_price,
                        historic_date=historic_date,
                        figi=figi,
                        strategy_id=strategy_id
                    )

    print('✅Historic_signals_SMA_are_saved to CSV')


def calc_one_figi_signals_rsi(sr_rsi: Series,
                              figi: str,
                              upper_rsi: float,
                              lower_rsi: float,
                              df_close_prices: DataFrame,
                              df_shares: DataFrame) -> DataFrame:
    df = DataFrame(columns=columns_rsi)
    size_of_df = len(sr_rsi)  # ограничиваем окно подсчета сигналов 20-тью днями
    if size_of_df >= 20:
        size_of_df = 20

    for y in range(-1, -size_of_df, -1):
        rsi_float = sr_rsi[y]
        historic_date_rsi = sr_rsi.index[y]
        historic_last_price_rsi = df_close_prices[figi][historic_date_rsi]

        if isna(historic_last_price_rsi):  # если close_price пустая, берёт данные за последние 4 дня
            for f in range(1, 5):
                historic_date_rsi_2 = sr_rsi.index[y - f]
                historic_last_price_rsi = df_close_prices[figi][historic_date_rsi_2]

        if rsi_float >= upper_rsi or rsi_float <= lower_rsi:  # если истина, записываем в DF сигнал
            buy_flag = 0 if rsi_float >= upper_rsi else 1
            [df, hist_signal] = save_signal_to_df(buy_flag=buy_flag, last_price=historic_last_price_rsi, figi=figi,
                                                  date_time=historic_date_rsi, strategy_id='rsi', df_shares=df_shares,
                                                  df=df, rsi_float=rsi_float)

    return df


def calc_rsi_float(df_close_prices: DataFrame) -> DataFrame:
    """Расчет по формуле RSI"""

    # for figi in figi_list:
    #     candles = HistoricCandle.get_candles_by_figi(figi=figi)
    #     if len(candles) < period:
    #         continue
    #     close_prices_list = list(map(lambda candle: [candle.close_price], candles))
    #     datetime_list = list(map(lambda candle: candle.date_time, candles))
    #     df_historic_prices = DataFrame(index=datetime_list, data=close_prices_list, columns=['close_price'])
    #     df_sma = df_historic_prices.rolling(period - 1).mean().dropna().round(3)
    #     for index in df_sma.index:
    #         MovingAverage.create(
    #             value=df_sma.close_price[index],
    #             figi=figi,
    #             period=period - 1,
    #             date_time=index
    #         )

    delta = df_close_prices.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period_of_ema, adjust=False).mean()
    ema_down = down.ewm(com=period_of_ema, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = (100 - (100 / (1 + rs))).round(2)
    rsi.to_csv(path_or_buf='csv/rsi.csv', sep=';')

    return rsi


def calc_historic_signals_rsi(df_close_prices: DataFrame,
                              df_shares: DataFrame,
                              df_rsi: DataFrame) -> DataFrame:
    """Функция позволяет рассчитать индикатор RSI и сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    print('⏩Historic signals RSI calc starts')
    for figi in df_close_prices.columns:
        # верхняя граница RSI, значение 95 отсеивает RSI примерно выше 70
        upper_rsi = nanpercentile(df_rsi[figi], upper_rsi_percentile)
        # нижняя граница RSI, значение 2.5 отсеивает RSI примерно ниже 30
        lower_rsi = nanpercentile(df_rsi[figi], lower_rsi_percentile)

        df_historic_signals_rsi = calc_one_figi_signals_rsi(sr_rsi=df_rsi[figi],
                                                            figi=figi,
                                                            upper_rsi=upper_rsi,
                                                            lower_rsi=lower_rsi,
                                                            df_close_prices=df_close_prices,
                                                            df_shares=df_shares)

        yield df_historic_signals_rsi


def save_historic_signals_rsi(df_close_prices: DataFrame,
                              df_shares: DataFrame):
    """Обеспечивает сохранение сигналов в DataFrame и CSV"""

    df_rsi = calc_rsi_float(df_close_prices=df_close_prices)
    list_df = calc_historic_signals_rsi(
        df_close_prices=df_close_prices,
        df_shares=df_shares,
        df_rsi=df_rsi
    )
    df_historic_signals_rsi = concat(objs=list_df, ignore_index=True, copy=False)

    # Сортировка по дате. В конце самые актуальные сигналы
    df_historic_signals_rsi.sort_values(by='datetime', inplace=True)
    df_historic_signals_rsi.reset_index(drop=True, inplace=True)
    df_historic_signals_rsi.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')
    print('✅Historic signals RSI are saved')


def calc_profit(df_historic_signals_rsi: DataFrame,
                figi_list: List,
                df_historic_signals_sma: DataFrame) -> None:
    """Считает доходность от использования двух последних сигналов SMA и RSI"""

    df_profit_sma = DataFrame(columns=['profit'])
    df_profit_rsi = DataFrame(columns=['profit'])
    profit = 'error'

    for figi in figi_list:
        try:
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

        try:
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
                 (now_msk() - timedelta(hours=1, minutes=45)).date())):
            df_historic_signals_sma = df
        else:
            df_historic_signals_sma = calc_historic_signals_sma(
                strategy_id=f'sma_{sma_periods.short}_{sma_periods.long}'
            )
    else:
        df_historic_signals_sma = calc_historic_signals_sma(
            strategy_id=f'sma_{sma_periods.short}_{sma_periods.long}'
        )