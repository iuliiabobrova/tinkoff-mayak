import asyncio
from decimal import Decimal
from typing import List, Iterator, NoReturn, Optional, AsyncGenerator

from asgiref.sync import sync_to_async

from pandas import DataFrame, Series

from corestrategy.settings import std_period, RsiSetting
from tgbot.models import (
    HistoricCandle,
    MovingAverage,
    StandardDeviation,
    Share,
    Signal,
    Strategy,
    RelativeStrengthIndex, StrategyRSI
)

from django.db.models import QuerySet


class SMASignalsCalculator:
    """
    Считает исторические сигналы по стратегии cross-SMA и сохраняет их в БД.

    :param strategy: Определяет стратегию, которая будет использоваться для расчетов.
    :param figi: Бумага по которой нужен расчет.
    """

    def __init__(self,
                 figi: str,
                 strategy: Strategy):
        self.figi = figi
        self.strategy = strategy

    # TODO заложить логику расчета не всех sma каждый раз (на будущее)
    # TODO заложить логику расчета свечей разных интервалов (parameter: interval) (на будущее)
    async def calc_indicator(self,
                             df_historic_close_prices: DataFrame) -> NoReturn:
        """
        Функция считает простое скользящее среднее

        :param df_historic_close_prices: DataFrame с историческими ценами закрытия свеч,
        Сформировать DF поможет def closeprices_dataframe_for_figi.
        """

        async def _calc_indicator() -> NoReturn:
            print(df_historic_close_prices.size)
            if df_historic_close_prices.size < ma_length:
                print(f'not enough data to calc sma for {self.figi}')
                return  # not enough data to calc
            df_sma = df_historic_close_prices.rolling(ma_length - 1).mean().dropna().round(3)
            print()

            async def _ma_generator() -> List[MovingAverage]:  # TODO async?

                def _generator() -> AsyncGenerator:
                    for index in df_sma.index:
                        yield MovingAverage(
                            value=df_sma.close_price[index],
                            share=share,
                            date_time=index,
                            period=ma_length - 1,
                            candle_interval=self.strategy.candle_interval
                        )

                return [ma async for ma in _generator()]

            await MovingAverage.objects.all().adelete()
            print(f'delete complete, {self.figi}')
            print(f'try to add to DB: {asyncio.ensure_future(_ma_generator())}')
            await MovingAverage.objects.abulk_create(objs=asyncio.ensure_future(_ma_generator()))
            print(f'saved ma {len(df_sma)}, {self.figi}')

        share = Share.objects.aget(figi=self.figi)
        for ma_length in [self.strategy.period.short, self.strategy.period.long]:
            print(f'⏩Start calculating SMA-float: {ma_length} for {self.figi}')
            await _calc_indicator()
        print(f'✅Calc of SMA done for {self.figi}')

    @sync_to_async()
    def get_short_sma_set(self) -> QuerySet[MovingAverage]:
        return MovingAverage.objects.filter(
            figi=self.figi,
            period=self.strategy.period.short,
            interval=self.strategy.candle_interval
        )[:20]  # ограничиваем окно подсчета сигналов 20-тью днями TODO

    @sync_to_async()
    def get_long_sma_set(self) -> QuerySet[MovingAverage]:
        return MovingAverage.objects.filter(
            figi=self.figi,
            period=self.strategy.period.long,
            interval=self.strategy.candle_interval
        )[:20]  # ограничиваем окно подсчета сигналов 20-тью днями TODO

    @staticmethod
    def check_sma_cross(short_sma_value: Decimal,
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
        print(f'⏩Historic signals SMA-cross {self.strategy.period} for {self.figi} calc starts')

        def _ma_signals_generator(self) -> Iterator[Signal]:  # TODO async
            for index_of_row in range(-1, -len(long_sma_set), -1):
                short_sma_value = short_sma_set[index_of_row].value
                previous_short_sma_value = short_sma_set[index_of_row - 1].value
                long_sma_value = long_sma_set[index_of_row].value
                previous_long_sma_value = long_sma_set[index_of_row - 1].value

                date_time = short_sma_set[index_of_row].date_time
                historic_price = HistoricCandle.objects.filter(figi=self.figi, date_time=date_time)

                buy_flag = self.check_sma_cross(
                    short_sma_value=short_sma_value,
                    previous_short_sma_value=previous_short_sma_value,
                    long_sma_value=long_sma_value,
                    previous_long_sma_value=previous_long_sma_value,
                    historic_price=historic_price
                )
                if buy_flag is not None:
                    yield Signal(
                        share=Share.objects.aget(figi=self.figi),
                        date_time=date_time,
                        historic_price=historic_price,
                        buy_flag=buy_flag,
                        strategy_id=self.periods.__str__
                    )

        @sync_to_async()
        def _filter_and_delete() -> QuerySet[Signal]:
            return Signal.objects.filter(strategy_id=self.strategy.id_, share__figi=self.figi).delete()

        await _filter_and_delete()
        short_sma_set = await self.get_short_sma_set()
        long_sma_set = await self.get_long_sma_set()
        await Signal.objects.abulk_create(objs=_ma_signals_generator(self))

        print('✅Historic_signals_SMA_are_saved')


class RSISignalsCalculator:

    def __init__(self,
                 strategy: StrategyRSI,
                 figi: str):
        """
        :param strategy: Определяет стратегию, которая будет использоваться для расчетов.
        :param figi: Бумага по которой нужен расчет.
        """

        self.figi = figi
        self.strategy = strategy

    async def calc_indicator(self, df_historic_close_prices: DataFrame) -> DataFrame:
        """Расчет индикатора RelativeStrengthIndex"""

        print(df_historic_close_prices)  # TODO delete
        print(type(df_historic_close_prices))  # TODO delete

        delta = df_historic_close_prices.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=RsiSetting.period_of_daily_ema, adjust=False).mean()
        ema_down = down.ewm(com=RsiSetting.period_of_daily_ema, adjust=False).mean()
        rs = ema_up / ema_down
        rsi = (100 - (100 / (1 + rs))).round(2)

        def rsi_generator(df_rsi) -> Iterator[RelativeStrengthIndex]:  # TODO async
            share = Share.objects.get(figi=self.figi)
            for index in df_rsi.index:
                yield RelativeStrengthIndex(
                    value=df_rsi.close_price[index],
                    share=share,
                    date_time=index,
                    period=self.strategy.period,
                    candle_interval=self.strategy.candle_interval
                )

        await RelativeStrengthIndex.objects.all().adelete()
        await RelativeStrengthIndex.objects.abulk_create(objs=rsi_generator(rsi))

        return rsi

    async def calc_one_figi_signals_rsi(self,
                                        df_rsi: DataFrame,
                                        df_historic_close_prices: DataFrame) -> NoReturn:

        size_of_df = len(df_rsi)
        size_of_df = 20 if size_of_df >= 20 else size_of_df  # ограничиваем окно подсчета сигналов 20-тью днями TODO
        share = Share.objects.aget(figi=self.figi)

        def _signals_generator() -> Iterator[Signal]:  # TODO async
            for y in range(-1, -size_of_df, -1):
                rsi_float = df_rsi[y]
                historic_date_rsi = df_rsi.index[y]
                historic_last_price_rsi = df_historic_close_prices[self.figi][historic_date_rsi]

                if rsi_float >= self.strategy.upper_rsi_border or rsi_float <= self.strategy.lower_rsi_border:
                    buy_flag = 0 if rsi_float >= self.strategy.lower_rsi_border else 1  # проверяем направление сигнала
                    yield Signal(
                        share=share,
                        date_time=historic_date_rsi,
                        historic_price=historic_last_price_rsi,
                        buy_flag=buy_flag,
                        strategy_id=self.strategy.id_,
                        profit=0  # TODO (на будущее)
                    )

        @sync_to_async()
        def _filter_and_delete() -> QuerySet[Signal]:
            return Signal.objects.filter(strategy_id=self.strategy.id_, share__figi=self.figi).delete()

        await _filter_and_delete()
        await Signal.objects.abulk_create(objs=_signals_generator())


def calc_profit(
        df_historic_signals_rsi: DataFrame,
        figi_list: List,
        df_historic_signals_sma: DataFrame
) -> NoReturn: # TODO (на будущее)
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
            # TODO заменить try-except на if (когда нет сигналов по бумаге) (на будущее)
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
            # TODO заменить try-except на if (когда нет сигналов по бумаге) (на будущее)
            pass

    df_profit_sma.to_csv(path_or_buf='csv/historic_profit_sma.csv', sep=';')
    df_profit_rsi.to_csv(path_or_buf='csv/historic_profit_rsi.csv', sep=';')
    print('✅Calculation_of_profit_is_done')


def calc_std_deviation(figi_list: List[str]): # TODO (на будущее)
    """Считает стандартное отклонение"""
    for figi in figi_list:
        candles = HistoricCandle.get_candles_by_figi(figi=figi)
        if len(candles) < std_period:
            continue
        close_prices_series = Series(list(map(lambda candle: [candle.close_price], candles)))
        std_deviation = close_prices_series.tail(std_period).pct_change().std().round(3)
        StandardDeviation.create(value=std_deviation, figi=figi, period=std_period)
    print('✅Calc of standard deviation done')
