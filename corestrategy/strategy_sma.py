from pandas import DataFrame
from typing import List

from corestrategy.utils import now_msk
from tgbot.models import Strategy


def sma_cross(actual_short_sma: float,
              actual_long_sma: float,
              figi: str,
              last_price: float,
              df_shares: DataFrame,
              df_previous_sma: DataFrame,
              df_hist_sgnls: DataFrame,
              sma_periods: Strategy.SMACrossPeriods,
              df_actual_signals: DataFrame) -> List:
    """Функция считает, пересекаются ли скользящие средние, а далее формирует и сохраняет сигнал"""

    strategy_id = f'sma_{sma_periods.short}_{sma_periods.long}'

    # из DF берем SMA по figi (SMA, предшествующие актуальным)
    previous_short_sma_2 = df_previous_sma.loc[figi].previous_short_sma
    previous_long_sma_2 = df_previous_sma.loc[figi].previous_long_sma

    # проверка на совпадение с условиями сигнала
    crossing_buy = ((actual_short_sma > actual_long_sma) & (previous_short_sma_2 < previous_long_sma_2) & (
            last_price > actual_long_sma))
    crossing_sell = ((actual_short_sma < actual_long_sma) & (previous_short_sma_2 > previous_long_sma_2) & (
            last_price < actual_long_sma))

    # если условие выполняется, то записываем данные в DataFrame
    if crossing_buy or crossing_sell:
        buy_flag = 0 if crossing_sell else 1
        sr_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1)
        if not sr_last_signal.empty:
            if buy_flag == 1 and sr_last_signal.buy_flag.all() != 1:
                [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag, last_price=last_price,
                                                                       figi=figi,
                                                                       date_time=now_msk(), strategy_id=strategy_id,
                                                                       df_shares=df_shares, df=df_hist_sgnls,
                                                                       df_actual_signals=df_actual_signals)
                df_hist_sgnls.to_csv(
                    path_or_buf=f'csv/historic_signals_sma_{sma_periods.short}_{sma_periods.long}.csv',
                    sep=';'
                )
            elif buy_flag == 0 and sr_last_signal.buy_flag.all() != 0:
                [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag, last_price=last_price,
                                                                       figi=figi,
                                                                       date_time=now_msk(), strategy_id=strategy_id,
                                                                       df_shares=df_shares, df=df_hist_sgnls,
                                                                       df_actual_signals=df_actual_signals)
                df_hist_sgnls.to_csv(
                    path_or_buf=f'csv/historic_signals_sma_{sma_periods.short}_{sma_periods.long}.csv',
                    sep=';'
                )
        else:
            [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag, last_price=last_price, figi=figi,
                                                                   date_time=now_msk(), strategy_id=strategy_id,
                                                                   df_shares=df_shares, df=df_hist_sgnls,
                                                                   df_actual_signals=df_actual_signals)
            df_hist_sgnls.to_csv(
                path_or_buf=f'csv/historic_signals_sma_{sma_periods.short}_{sma_periods.long}.csv',
                sep=';'
            )

    return [df_hist_sgnls, df_actual_signals]


def calc_actual_signals_sma(n: int,
                            df_shares: DataFrame,
                            df_hist_signals_sma: DataFrame,
                            df_all_lasts: DataFrame,
                            df_historic_sma: DataFrame,
                            df_previous_sma: DataFrame,
                            sma_periods: Strategy.SMACrossPeriods,
                            df_actual_signals: DataFrame) -> List[DataFrame]:
    """Функция получает из SMA.csv исторические скользящие средние. Далее по ластам считает актуальные скользящие.
    Все данные в итоге подаёт на вход def sma_cross"""

    if not df_all_lasts.empty:
        for figi in df_all_lasts.index:

            # подготовка DF с short_SMA и long_SMA по figi
            if any([x == f'{figi}.short' for x in df_historic_sma.columns]):
                df_hist_short_sma = df_historic_sma[f'{figi}.short'].dropna()
                df_hist_long_sma = df_historic_sma[f'{figi}.long'].dropna()

                if (not df_hist_short_sma.empty) and (not df_hist_long_sma.empty):  # проверка на пустой DF
                    hist_short_sma = df_hist_short_sma.loc[df_hist_short_sma.index.max()]  # последняя короткая SMA
                    hist_long_sma = df_hist_long_sma.loc[df_hist_long_sma.index.max()]  # последняя длинная SMA

                    last_price = df_all_lasts.loc[figi].last_price

                    if n == 0:
                        previous_short_sma = round((
                                (hist_short_sma * (sma_periods.short - 1) + last_price) / sma_periods.short), 3)
                        previous_long_sma = round((
                                (hist_long_sma * (sma_periods.long - 1) + last_price) / sma_periods.long), 3)
                        df_previous_sma.loc[figi] = [previous_short_sma, previous_long_sma]

                    else:
                        # подготовка актуальных SMA
                        actual_short_sma = round((
                                (hist_short_sma * (sma_periods.short - 1) + last_price) / sma_periods.short), 3)
                        actual_long_sma = round((
                                (hist_long_sma * (sma_periods.long - 1) + last_price) / sma_periods.long), 3)

                        [df_hist_signals_sma, df_actual_signals] = sma_cross(
                            actual_short_sma=actual_short_sma,
                            actual_long_sma=actual_long_sma,
                            figi=figi, last_price=last_price,
                            df_shares=df_shares,
                            df_previous_sma=df_previous_sma,
                            df_hist_sgnls=df_hist_signals_sma,
                            sma_periods=sma_periods,
                            df_actual_signals=df_actual_signals
                        )

                        # актуальные SMA становятся прошлыми
                        df_previous_sma.loc[figi] = [actual_short_sma, actual_long_sma]

    return [df_hist_signals_sma, df_previous_sma, df_actual_signals]
