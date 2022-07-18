from pandas import DataFrame
from typing import List

from corestrategy.historic_data_download import period_of_short_sma, period_of_long_sma
from corestrategy.utils import save_signal_to_df, _now, get_n_digits
from corestrategy.deliery_boy import send_signal_to_strategy_subscribers


def sma_cross(actual_short_sma: float,
              actual_long_sma: float,
              figi: str,
              last_price: float,
              df_shares: DataFrame,
              df_previous_sma: DataFrame,
              df_hist_sgnls: DataFrame) -> DataFrame:
    """Функция считает, пересекаются ли скользящие средние, а далее формирует и сохраняет сигнал"""

    # из DF берем SMA по figi (SMA, предшествующие актуальным)
    previous_short_sma_2 = df_previous_sma.loc[figi].previous_short_sma
    previous_long_sma_2 = df_previous_sma.loc[figi].previous_long_sma

    # проверка на совпадение с условиями сигнала
    crossing_buy = ((actual_short_sma > actual_long_sma) & (previous_short_sma_2 < previous_long_sma_2) & (
            last_price > actual_long_sma))
    crossing_sell = ((actual_short_sma < actual_long_sma) & (previous_short_sma_2 > previous_long_sma_2) & (
            last_price < actual_long_sma))

    # если условие выполняется, то записываем данные в DataFrame
    if crossing_buy:
        df_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1)
        if not df_last_signal.empty:
            if df_last_signal.buy_flag.all() != 1:
                df_hist_sgnls = save_signal_to_df(buy_flag=1, sell_flag=0, last_price=last_price, figi=figi,
                                                  date=_now(), strategy='sma', df_shares=df_shares, df=df_hist_sgnls)
                send_signal_to_strategy_subscribers(df=df_hist_sgnls)
        else:
            df_hist_sgnls = save_signal_to_df(buy_flag=1, sell_flag=0, last_price=last_price, figi=figi, date=_now(),
                                              strategy='sma', df_shares=df_shares, df=df_hist_sgnls)
            send_signal_to_strategy_subscribers(df=df_hist_sgnls)

    if crossing_sell:
        df_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1)
        if not df_last_signal.empty:
            if df_last_signal.sell_flag.all() != 1:
                df_hist_sgnls = save_signal_to_df(buy_flag=0, sell_flag=1, last_price=last_price, figi=figi,
                                                  date=_now(), strategy='sma', df_shares=df_shares, df=df_hist_sgnls)
                send_signal_to_strategy_subscribers(df=df_hist_sgnls)
        else:
            df_hist_sgnls = save_signal_to_df(buy_flag=0, sell_flag=1, last_price=last_price, figi=figi, date=_now(),
                                              strategy='sma', df_shares=df_shares, df=df_hist_sgnls)
            send_signal_to_strategy_subscribers(df=df_hist_sgnls)

    return df_hist_sgnls


def calc_actual_signals_sma(n: int,
                            df_shares: DataFrame,
                            df_hist_signals_sma: DataFrame,
                            df_all_lasts: DataFrame,
                            df_historic_sma: DataFrame,
                            df_previous_sma: DataFrame) -> List[DataFrame]:
    """Функция получает из SMA.csv исторические скользящие средние. Далее по ластам считает актуальные скользящие.
    Все данные в итоге подаёт на вход def sma_cross"""

    if not df_all_lasts.empty:
        for figi in df_all_lasts.index:

            figi = figi[:12]  # считываем figi без лишних элементов

            # подготовка DF с short_SMA и long_SMA по figi
            if any(x == f'{figi}.short' for x in df_historic_sma.columns):
                df_hist_short_sma = df_historic_sma[f'{figi}.short'].dropna()
                df_hist_long_sma = df_historic_sma[f'{figi}.long'].dropna()

                if (not df_hist_short_sma.empty) and (not df_hist_long_sma.empty):  # проверка на пустой DF
                    hist_short_sma = df_hist_short_sma.loc[df_hist_short_sma.index.max()]  # последняя короткая SMA
                    hist_long_sma = df_hist_long_sma.loc[df_hist_long_sma.index.max()]  # последняя длинная SMA

                    last_price = df_all_lasts.loc[figi].last_price
                    ndigits = get_n_digits(last_price)
                    if last_price // 1 == last_price:
                        last_price = int(last_price)
                    else:
                        last_price = round(float(last_price), ndigits)

                    if n == 0:
                        previous_short_sma = round((
                                (hist_short_sma * (period_of_short_sma - 1) + last_price) / period_of_short_sma), 3)
                        previous_long_sma = round((
                                (hist_long_sma * (period_of_long_sma - 1) + last_price) / period_of_long_sma), 3)
                        df_previous_sma.loc[figi] = [previous_short_sma, previous_long_sma]

                    else:
                        # подготовка актуальных SMA
                        actual_short_sma = round((
                                (hist_short_sma * (period_of_short_sma - 1) + last_price) / period_of_short_sma), 3)
                        actual_long_sma = round((
                                (hist_long_sma * (period_of_long_sma - 1) + last_price) / period_of_long_sma), 3)

                        df_hist_signals_sma = sma_cross(actual_short_sma=actual_short_sma,
                                                        actual_long_sma=actual_long_sma,
                                                        figi=figi, last_price=last_price,
                                                        df_shares=df_shares,
                                                        df_previous_sma=df_previous_sma,
                                                        df_hist_sgnls=df_hist_signals_sma)

                        # актуальные SMA становятся прошлыми
                        df_previous_sma.loc[figi] = [actual_short_sma, actual_long_sma]

    df_hist_signals_sma.to_csv(path_or_buf='csv/historic_signals_sma.csv', sep=';')

    return [df_hist_signals_sma, df_previous_sma]
