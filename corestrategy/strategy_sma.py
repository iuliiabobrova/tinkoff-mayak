from datetime import datetime
from pandas import DataFrame, read_csv
from typing import Tuple

from corestrategy.historic_data_download import period_of_short_sma, period_of_long_sma
from corestrategy.utils import save_signal_to_df


def sma_cross(actual_short_sma: float,
              actual_long_sma: float,
              figi: str,
              last_price: float,
              df_shares: DataFrame,
              df_previous_sma: DataFrame,
              df_actual_signals_sma: DataFrame,
              df_hist_signals_sma: DataFrame) -> Tuple[DataFrame, DataFrame]:
    """Функция считает, пересекаются ли скользящие средние, а далее формирует и сохраняет сигнал"""

    global columns_sma
    # из DF с SMA берем определенные по figi (SMA предшествуют актуальным)
    previous_short_sma_2 = df_previous_sma.loc[figi].previous_short_sma
    previous_long_sma_2 = df_previous_sma.loc[figi].previous_long_sma

    # проверка на совпадение с условиями сигнала
    crossing_buy = ((actual_short_sma > actual_long_sma) & (previous_short_sma_2 < previous_long_sma_2) & (
            last_price > actual_long_sma))
    crossing_sell = ((actual_short_sma < actual_long_sma) & (previous_short_sma_2 > previous_long_sma_2) & (
            last_price < actual_long_sma))

    # если условие выполняется, то записываем данные в CSV
    if crossing_sell:
        if (df_actual_signals_sma.figi == figi).any():  # TODO проверить возможность удалить условие
            if df_actual_signals_sma[df_actual_signals_sma.figi == figi].tail(1).sell_flag.all() != 1:
                df_actual_signals_sma = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                          figi=figi, date=datetime.utcnow(), strategy='sma',
                                                          df=df_hist_signals_sma, df_shares=df_shares)
                df_hist_signals_sma = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                        figi=figi, date=datetime.utcnow(), strategy='sma',
                                                        df=df_hist_signals_sma, df_shares=df_shares)

        else:
            df_actual_signals_sma = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                      figi=figi, date=datetime.utcnow(), strategy='sma',
                                                      df=df_hist_signals_sma, df_shares=df_shares)
            df_hist_signals_sma = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                    figi=figi, date=datetime.utcnow(), strategy='sma',
                                                    df=df_hist_signals_sma, df_shares=df_shares)
    if crossing_buy:
        if (df_actual_signals_sma.figi == figi).any():  # TODO проверить возможность удалить условие
            if df_actual_signals_sma[df_actual_signals_sma.figi == figi].tail(1).buy_flag.all() != 1:
                df_actual_signals_sma = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                          figi=figi, date=datetime.utcnow(), strategy='sma',
                                                          df=df_hist_signals_sma, df_shares=df_shares)
                df_hist_signals_sma = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                        figi=figi, date=datetime.utcnow(), strategy='sma',
                                                        df=df_hist_signals_sma, df_shares=df_shares)

        else:
            df_actual_signals_sma = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                      figi=figi, date=datetime.utcnow(), strategy='sma',
                                                      df=df_hist_signals_sma, df_shares=df_shares)
            df_hist_signals_sma = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                    figi=figi, date=datetime.utcnow(), strategy='sma',
                                                    df=df_hist_signals_sma, df_shares=df_shares)

    return df_actual_signals_sma, df_hist_signals_sma


def calc_actual_signals_sma(n: int,
                            figi_list: list,
                            df_shares: DataFrame,
                            df_historic_signals_sma: DataFrame,
                            df_actual_signals_sma: DataFrame,
                            df_all_lasts: DataFrame) -> tuple:
    """Функция получает из SMA.csv исторические скользящие средние. Далее по ластам считает актуальные скользящие.
    Все данные в итоге подаёт на вход def sma_cross"""

    # подготовка df
    df_previous_sma_saving = DataFrame(index=figi_list,
                                       columns=['previous_short_sma', 'previous_long_sma'])
    df_all_historic_sma = read_csv(filepath_or_buffer='csv/sma.csv',
                                   sep=';',
                                   index_col=0)

    for figi in df_all_historic_sma.columns[::2]:
        figi = figi[:12]  # считываем figi без лишних элементов

        # подготовка DF с short_SMA по figi
        df_historic_short_sma = df_all_historic_sma[f'{figi}.short'].dropna()
        if df_historic_short_sma.size != 0:  # проверка на пустой DF
            historic_short_sma = df_historic_short_sma.loc[
                df_historic_short_sma.index.max()]  # закладываем в переменную последнюю короткую SMA
        else:
            historic_short_sma = False

        # подготовка DF с long_SMA по figi
        df_historic_long_sma = df_all_historic_sma[f'{figi}.long'].dropna()
        if df_historic_long_sma.size != 0:  # проверка на пустой DF
            historic_long_sma = df_historic_long_sma.loc[
                df_historic_long_sma.index.max()]  # закладываем в переменную последнюю длинную SMA
        else:
            historic_long_sma = False

        # ниже получаем актуальные данные о last_price из df_all_lasts и считаем актуальные SMA
        a = datetime.utcnow().year == df_all_lasts.loc[figi].datetime.year
        b = datetime.utcnow().month == df_all_lasts.loc[figi].datetime.month
        c = datetime.utcnow().day == df_all_lasts.loc[figi].datetime.day
        d = datetime.utcnow().hour == df_all_lasts.loc[figi].datetime.hour
        e = datetime.utcnow().minute == df_all_lasts.loc[figi].datetime.minute
        f = datetime.utcnow().minute - 1 == df_all_lasts.loc[figi].datetime.minute
        g = datetime.utcnow().minute - 2 == df_all_lasts.loc[figi].datetime.minute
        h = e or f or g
        if a and b and c and d and h:

            last_price = float(df_all_lasts.loc[figi].last_price)
            if n == 0:
                previous_short_sma = round((
                        (historic_short_sma * (period_of_short_sma - 1) + last_price) / period_of_short_sma), 3)
                previous_long_sma = round((
                        (historic_long_sma * (period_of_long_sma - 1) + last_price) / period_of_long_sma), 3)
                df_previous_sma_saving.loc[figi] = [
                    previous_short_sma, previous_long_sma]

            else:

                actual_short_sma = round((
                        (historic_short_sma * (period_of_short_sma - 1) + last_price) / period_of_short_sma), 3)
                actual_long_sma = round((
                        (historic_long_sma * (period_of_long_sma - 1) + last_price) / period_of_long_sma), 3)
                df_previous_sma_saving.loc[figi] = [actual_short_sma,
                                                    actual_long_sma]  # актуальные сигналы становятся прошлыми

                df_actual_signals_sma, df_historic_signals_sma = sma_cross(actual_short_sma=actual_short_sma,
                                                                           actual_long_sma=actual_long_sma, figi=figi,
                                                                           last_price=last_price, df_shares=df_shares,
                                                                           df_previous_sma=df_previous_sma_saving,
                                                                           df_actual_signals_sma=df_actual_signals_sma,
                                                                           df_hist_signals_sma=df_historic_signals_sma)

    df_actual_signals_sma.to_csv(path_or_buf='csv/actual_signals_sma.csv', sep=';')
    df_historic_signals_sma.to_csv(path_or_buf='csv/historic_signals_sma.csv', sep=';')

    return df_actual_signals_sma, df_historic_signals_sma
