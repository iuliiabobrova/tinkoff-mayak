from pandas import DataFrame
from numpy import nanpercentile

from corestrategy.settings import *
from corestrategy.utils import save_signal_to_df, _now
from corestrategy.deliery_boy import send_signal_to_strategy_subscribers


def calc_actual_signals_rsi(df_shares: DataFrame,
                            figi_list: list,
                            df_hist_sgnls: DataFrame,
                            df_all_lasts: DataFrame,
                            df_close_prices: DataFrame) -> DataFrame:
    """Функция позволяет рассчитать индикатор RSI и актуальные сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    upper_rsi = upper_rsi_fix
    lower_rsi = lower_rsi_fix

    for figi in figi_list:
        if (df_all_lasts.index == figi).any():
            df_figi_close_prices = df_close_prices[f'{figi}'].dropna()[-1:-365:-1][::-1]
            last_price = float(df_all_lasts.loc[figi].last_price)
            df_figi_close_prices.loc[_now()] = last_price

            # расчет по формуле RSI
            delta = df_figi_close_prices.diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=period_of_ema, adjust=False).mean().tail(1)
            ema_down = down.ewm(com=period_of_ema, adjust=False).mean().tail(1)
            rs = ema_up / ema_down
            rsi = (100 - (100 / (1 + rs))).round(4)

            # определение границ нормы RSI
            if settings_percentile:
                upper_rsi = nanpercentile(rsi, upper_rsi_percentile)  # верхняя граница RSI, выше только 5% высоких RSI
                lower_rsi = nanpercentile(rsi, lower_rsi_percentile)  # нижняя граница RSI, выше только 2.5% низких RSI

            if rsi[0] >= upper_rsi:  # если истина, записываем в DF сигнал на продажу
                df_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1)
                if not df_last_signal.empty:
                    if df_last_signal.sell_flag.all() != 1 and df_last_signal.datetime.all() != _now():
                        date = rsi.index[-1]
                        df_hist_sgnls = save_signal_to_df(buy_flag=0,
                                                          sell_flag=1,
                                                          x=figi,
                                                          last_price=last_price,
                                                          figi=figi,
                                                          date=date,
                                                          strategy='rsi',
                                                          rsi_float=rsi,
                                                          df_shares=df_shares,
                                                          df=df_hist_sgnls)
                        send_signal_to_strategy_subscribers(df=df_hist_sgnls)
                else:
                    date = rsi.index[-1]
                    df_hist_sgnls = save_signal_to_df(buy_flag=0,
                                                      sell_flag=1,
                                                      x=figi,
                                                      last_price=last_price,
                                                      figi=figi,
                                                      date=date,
                                                      strategy='rsi',
                                                      rsi_float=rsi,
                                                      df_shares=df_shares,
                                                      df=df_hist_sgnls)
                    send_signal_to_strategy_subscribers(df=df_hist_sgnls)

            if rsi[0] <= lower_rsi:  # если истина, записываем в DF сигнал на покупку
                df_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1)
                if not df_last_signal.empty:
                    if df_last_signal.buy_flag.all() != 1 and df_last_signal.datetime.all() != _now():
                        date = rsi.index[-1]
                        df_hist_sgnls = save_signal_to_df(buy_flag=1,
                                                          sell_flag=0,
                                                          x=figi,
                                                          last_price=last_price,
                                                          figi=figi,
                                                          date=date,
                                                          strategy='rsi',
                                                          rsi_float=rsi,
                                                          df_shares=df_shares,
                                                          df=df_hist_sgnls)
                        send_signal_to_strategy_subscribers(df=df_hist_sgnls)
                else:
                    date = rsi.index[-1]
                    df_hist_sgnls = save_signal_to_df(buy_flag=1,
                                                      sell_flag=0,
                                                      x=figi,
                                                      last_price=last_price,
                                                      figi=figi,
                                                      date=date,
                                                      strategy='rsi',
                                                      rsi_float=rsi,
                                                      df_shares=df_shares,
                                                      df=df_hist_sgnls)
                    send_signal_to_strategy_subscribers(df=df_hist_sgnls)

    df_hist_sgnls.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

    return df_hist_sgnls
