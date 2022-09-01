from typing import List, Iterator, NoReturn, Optional
from numpy import nanpercentile

from pandas import DataFrame, Series, concat, isna
from tinkoff.invest import CandleInterval

from corestrategy.settings import std_period, RsiSetting
from corestrategy.historic_data_download import get_figi_list_with_inactual_historic_data
from tgbot.models import HistoricCandle, MovingAverage, StandardDeviation, Share, Signal, Strategy
from iteration_utilities import deepflatten

from django.db.models import Avg, F, RowRange, Window, QuerySet


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


# TODO заложить логику расчета не всех sma каждый раз
# TODO заложить логику расчета свечей разных интервалов (parameter: interval)
async def calc_sma(ma_length: int, figi_list: List[str], interval: CandleInterval = None):
    """
    Считает простое скользящее среднее

    :param ma_length: Длина скользящей средней.
    :param figi_list: Бумаги, по которым будет производиться расчет.
    :param interval: Интервал свеч (день, 1 минута, 5 минут и т.д.)
    """
    for figi in figi_list:
        candles = HistoricCandle.get_candles_by_figi(figi=figi)
        if len(candles) < ma_length:
            continue
        close_prices_list = list(map(lambda candle: [candle.close_price], candles))
        datetime_list = list(map(lambda candle: candle.date_time, candles))
        df_historic_prices = DataFrame(index=datetime_list, data=close_prices_list, columns=['close_price'])
        df_sma = df_historic_prices.rolling(ma_length - 1).mean().dropna().round(3)

        def ma_generator() -> Iterator[MovingAverage]:
            for index in df_sma.index:
                yield MovingAverage(
                    value=df_sma.close_price[index],
                    share=Share.objects.get(figi=figi),
                    date_time=index,
                    ma_length=ma_length - 1
                )

        MovingAverage.objects.all().delete()
        await MovingAverage.objects.abulk_create(objs=ma_generator())


# TODO ТЕСТОВАЯ ФУНКЦИЯ расчетов напрямую в БД, нужно доработать и заменить calc_sma
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
async def recalc_sma_if_inactual():
    print('⏩Start calculating SMA-float')
    list_of_ma_length = list(deepflatten([[periods.short, periods.long] for periods in Strategy.SMACrossPeriods.all()]))
    print("period_list", list_of_ma_length)
    for ma_length in list_of_ma_length:
        figi_list = get_figi_list_with_inactual_historic_data(MovingAverage, period=ma_length)
        await calc_sma(ma_length=ma_length, figi_list=figi_list)
    print('✅Calc of SMA done')


# TODO interval
def calc_historic_signals_sma(
        periods: Strategy.SMACrossPeriods,
        figi_list: List[str],
        interval: CandleInterval
):
    """
    Считает только исторические сигналы по стратегии cross-SMA.

    :param periods: Определяет длины скользящих средних. Например: SMACrossPeriods(50, 200).
    :param figi_list: Список figi, по которым нужен расчет.
    :param interval: Определяет интервал свеч. Например: дневные свечи = CandleInterval.CANDLE_INTERVAL_DAY
    """

    def get_short_sma_set() -> QuerySet[MovingAverage]:
        return MovingAverage.objects.filter(
            figi=figi,
            period=periods.short,
            interval=CandleInterval.CANDLE_INTERVAL_DAY
        )[20]

    def get_long_sma_set() -> QuerySet[MovingAverage]:
        return MovingAverage.objects.filter(
            figi=figi,
            period=periods.long,
            interval=CandleInterval.CANDLE_INTERVAL_DAY
        )[20]

    def sma_cross() -> Optional[bool]:
        """
        Проверяет: пересекаются ли скользящие средние.

        :return: Если скользящие пересекаются, функция возвращает bool-направление сигнала. Иначе None.
        """
        crossing_buy = (short_sma_value > long_sma_value) and \
                       (previous_short_sma_value < previous_long_sma_value) and \
                       (historic_price > long_sma_value)
        crossing_sell = ((short_sma_value < long_sma_value) and
                         (previous_short_sma_value > previous_long_sma_value) and
                         (historic_price < long_sma_value))
        if crossing_sell or crossing_buy:
            return False if crossing_sell else True
        else:
            return None

    print(f'⏩Historic signals {periods} calc starts')
    for figi in figi_list:
        short_sma_set = get_short_sma_set()
        long_sma_set = get_long_sma_set()

        for index_of_row in range(-1, -len(long_sma_set), -1):

            short_sma_value = short_sma_set[index_of_row].value
            previous_short_sma_value = short_sma_set[index_of_row - 1].value
            long_sma_value = long_sma_set[index_of_row].value
            previous_long_sma_value = long_sma_set[index_of_row - 1].value

            date_time = short_sma_set[index_of_row].date_time
            historic_price = HistoricCandle.objects.filter(figi=figi, date_time=date_time)

            # формирование сигнала, запись в DF
            buy_flag = sma_cross()
            if buy_flag is not None:
                Signal.objects.create(
                    share=Share.objects.get(figi=figi),
                    date_time=date_time,
                    historic_price=historic_price,
                    buy_flag=buy_flag,
                    strategy_id=periods.__str__
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
    ema_up = up.ewm(com=RsiSetting.period_of_daily_ema, adjust=False).mean()
    ema_down = down.ewm(com=RsiSetting.period_of_daily_ema, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = (100 - (100 / (1 + rs))).round(2)
    rsi.to_csv(path_or_buf='csv/rsi.csv', sep=';')

    return rsi


def calc_historic_signals_rsi(df_close_prices: DataFrame,
                              df_shares: DataFrame,
                              df_rsi: DataFrame):
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


def calc_profit(
        df_historic_signals_rsi: DataFrame,
        figi_list: List,
        df_historic_signals_sma: DataFrame
) -> NoReturn:
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
