from datetime import datetime as dt

from pandas import DataFrame, concat
from numpy import nanpercentile

from corestrategy.settings import *
from corestrategy.utils import save_signal_to_df


def calc_actual_signals_rsi(df_shares: DataFrame,
                            figi_list: list,
                            df_historic_signals_rsi: DataFrame,
                            df_actual_signals_rsi: DataFrame,
                            df_all_lasts: DataFrame,
                            df_close_prices: DataFrame) -> tuple:
    """Функция позволяет рассчитать индикатор RSI и актуальные сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    for figi in figi_list:
        df_figi_close_prices = df_close_prices[f'{figi}'].dropna()[-1:-365:-1][::-1]
        last_price = float(df_all_lasts.loc[figi].last_price)
        df_figi_close_prices.loc[dt.now()] = last_price

        # расчет по формуле RSI
        delta = df_figi_close_prices.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=period_of_ema, adjust=False).mean()
        ema_down = down.ewm(com=period_of_ema, adjust=False).mean()
        rs = ema_up / ema_down
        rsi = (100 - (100 / (1 + rs))).round(4)
        if settings_fix:
            upper_rsi = upper_rsi_fix
            lower_rsi = lower_rsi_fix
        if settings_percentile:
            upper_rsi = nanpercentile(rsi, upper_rsi_percentile)  # верхняя граница RSI, выше только 5% высоких RSI
            lower_rsi = nanpercentile(rsi, lower_rsi_percentile)  # нижняя граница RSI, выше только 2.5% низких RSI
        rsi_float = rsi[-1]

        if rsi_float > upper_rsi:  # если истина, записываем в DF сигнал на продажу
            if (df_actual_signals_rsi.figi == figi).any():  # TODO проверить возможность удаления условия
                if df_actual_signals_rsi[df_actual_signals_rsi.figi == figi].tail(1).sell_flag.all() != 1:
                    date = rsi.index[-1]
                    df_actual_signals_rsi = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                              figi=figi, date=date, strategy='rsi',
                                                              rsi_float=rsi_float, df_shares=df_shares)
                    df_historic_signals_rsi = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                                figi=figi, date=date, strategy='rsi',
                                                                rsi_float=rsi_float, df_shares=df_shares)
            else:
                date = rsi.index[-1]
                df_actual_signals_rsi = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                          figi=figi, date=date, strategy='rsi',
                                                          rsi_float=rsi_float, df_shares=df_shares)
                df_historic_signals_rsi = save_signal_to_df(buy_flag=0, sell_flag=1, x=figi, last_price=last_price,
                                                            figi=figi, date=date, strategy='rsi',
                                                            rsi_float=rsi_float, df_shares=df_shares)

        if rsi_float <= lower_rsi:  # если истина, записываем в DF сигнал на покупку
            if (df_actual_signals_rsi.figi == figi).any():  # TODO проверить возможность удаления условия
                if df_actual_signals_rsi[df_actual_signals_rsi.figi == figi].tail(1).buy_flag.all() != 1:
                    date = rsi.index[-1]
                    df_actual_signals_rsi = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                              figi=figi, date=date, strategy='rsi',
                                                              rsi_float=rsi_float, df_shares=df_shares)
                    df_historic_signals_rsi = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                                figi=figi, date=date, strategy='rsi',
                                                                rsi_float=rsi_float, df_shares=df_shares)
            else:
                date = rsi.index[-1]
                df_actual_signals_rsi = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                          figi=figi, date=date, strategy='rsi',
                                                          rsi_float=rsi_float, df_shares=df_shares)
                df_historic_signals_rsi = save_signal_to_df(buy_flag=1, sell_flag=0, x=figi, last_price=last_price,
                                                            figi=figi, date=date, strategy='rsi',
                                                            rsi_float=rsi_float, df_shares=df_shares)

    df_actual_signals_rsi.to_csv(path_or_buf='csv/actual_signals_rsi.csv', sep=';')
    df_historic_signals_rsi.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

    return df_actual_signals_rsi, df_historic_signals_rsi
