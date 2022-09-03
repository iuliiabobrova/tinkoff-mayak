import asyncio
from decimal import Decimal
from typing import List, Iterator, NoReturn, Optional, Tuple, Union

import tqdm.asyncio
from asgiref.sync import sync_to_async
from numpy import nanpercentile

from pandas import DataFrame, Series, concat, isna
from tinkoff.invest import CandleInterval

from corestrategy.settings import std_period, RsiSetting
from corestrategy.historic_data_download import get_figi_with_inactual_historic_data
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


# TODO заложить логику расчета не всех sma каждый раз
# TODO заложить логику расчета свечей разных интервалов (parameter: interval)
async def recalc_sma_if_inactual(
        figi_tuple: Union[Tuple[str], str] = None,
        interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY
) -> NoReturn:
    """
    Считает простое скользящее среднее

    :param interval: Интервал свеч (день, 1 минута, 5 минут и т.д.)
    :param figi_tuple: По каким акциям будет произведен расчет sma?
    Если параметр не указан, sma будут рассчитаны для всех акций с неактуальными историческими данными
    """

    async def calc_sma(figi_tuple_=figi_tuple) -> NoReturn:

        if figi_tuple_ is None:
            figi_tuple_ = await get_figi_with_inactual_historic_data(MovingAverage, period=ma_length)

        for figi in figi_tuple:
            candles = await HistoricCandle.get_candles_by_figi(figi=figi)
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
                        period=ma_length - 1,
                        candle_interval=interval
                    )

            await MovingAverage.objects.all().adelete()
            await MovingAverage.objects.abulk_create(objs=ma_generator())

    print('⏩Start calculating SMA-float')
    list_of_ma_length = list(deepflatten([[periods.short, periods.long] for periods in Strategy.SMACross.Periods.all()]))
    tasks = []
    for ma_length in list_of_ma_length:
        tasks.append(asyncio.create_task(calc_sma()))
    await asyncio.gather(*tasks)
    print('✅Calc of SMA done')


class SMASignalsCalculator:
    """
    Считает исторические сигналы по стратегии cross-SMA и сохраняет их в БД.

    :param periods: Определяет длины скользящих средних. Например: SMACross.Periods(50, 200).
    :param figi: бумага по которой нужен расчет.
    :param interval: Определяет интервал свеч. Например: дневные свечи = CandleInterval.CANDLE_INTERVAL_DAY
    """

    def __init__(self,
                 figi: str,
                 periods: Strategy.SMACross.Periods,
                 interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_DAY):
        self.figi = figi
        self.periods = periods
        self.interval = interval

    @sync_to_async()
    def get_short_sma_set(self) -> QuerySet[MovingAverage]:
        return MovingAverage.objects.filter(
            figi=self.figi,
            period=self.periods.short,
            interval=self.interval
        )[:20]

    @sync_to_async()
    def get_long_sma_set(self) -> QuerySet[MovingAverage]:
        return MovingAverage.objects.filter(
            figi=self.figi,
            period=self.periods.long,
            interval=self.interval
        )[:20]

    @staticmethod
    async def check_sma_cross(short_sma_value: Decimal,
                              previous_short_sma_value: Decimal,
                              long_sma_value: Decimal,
                              previous_long_sma_value: Decimal,
                              historic_price: Decimal) -> Optional[bool]:
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

    async def calc_historic_signals(self) -> NoReturn:
        print(f'⏩Historic signals for {self.figi}: {self.periods} calc starts')
        short_sma_set = await self.get_short_sma_set()
        long_sma_set = await self.get_long_sma_set()

        for index_of_row in range(-1, -len(long_sma_set), -1):

            short_sma_value = short_sma_set[index_of_row].value
            previous_short_sma_value = short_sma_set[index_of_row - 1].value
            long_sma_value = long_sma_set[index_of_row].value
            previous_long_sma_value = long_sma_set[index_of_row - 1].value

            date_time = short_sma_set[index_of_row].date_time
            historic_price = HistoricCandle.objects.filter(figi=self.figi, date_time=date_time)

            buy_flag = await self.check_sma_cross(
                short_sma_value=short_sma_value,
                previous_short_sma_value=previous_short_sma_value,
                long_sma_value=long_sma_value,
                previous_long_sma_value=previous_long_sma_value,
                historic_price=historic_price
            )
            if buy_flag is not None:
                await Signal.objects.acreate(
                    share=Share.objects.aget(figi=self.figi),
                    date_time=date_time,
                    historic_price=historic_price,
                    buy_flag=buy_flag,
                    strategy_id=self.periods.__str__
                )
        print('✅Historic_signals_SMA_are_saved')






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


def calc_rsi_float() -> NoReturn:
    """Расчет индикатора RelativeStrengthIndex"""

    df_close_prices = DataFrame.from_dict(HistoricCandle.objects.values_list('close_price'))
    print(df_close_prices)
    raise ValueError
    # delta = df_close_prices.diff()
    # up = delta.clip(lower=0)
    # down = -1 * delta.clip(upper=0)
    # ema_up = up.ewm(com=RsiSetting.period_of_daily_ema, adjust=False).mean()
    # ema_down = down.ewm(com=RsiSetting.period_of_daily_ema, adjust=False).mean()
    # rs = ema_up / ema_down
    # rsi = (100 - (100 / (1 + rs))).round(2)
    # rsi.to_csv(path_or_buf='csv/rsi.csv', sep=';')
    #
    # return rsi


def calc_historic_signals_rsi():
    """Функция позволяет рассчитать сигналы на основе индикатора RSI.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    аттрибутах класса RsiSetting"""

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
