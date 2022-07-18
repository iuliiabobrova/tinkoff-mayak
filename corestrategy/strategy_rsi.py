from pandas import DataFrame
from numpy import nanpercentile

from corestrategy.settings import *
from corestrategy.utils import save_signal_to_df, _now, get_last_price_from_df
from corestrategy.deliery_boy import send_signal_to_strategy_subscribers


def calc_actual_signals_rsi(df_shares: DataFrame,
                            df_hist_sgnls: DataFrame,
                            df_all_lasts: DataFrame,
                            df_close_prices: DataFrame) -> DataFrame:
    """Функция позволяет рассчитать индикатор RSI и актуальные сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    upper_rsi = upper_rsi_fix
    lower_rsi = lower_rsi_fix

    if not df_all_lasts.empty:
        for figi in df_all_lasts.index:

            df_figi_close_prices = df_close_prices[f'{figi}'].dropna()[-1:-365:-1][::-1]
            last_price = get_last_price_from_df(figi=figi, df=df_all_lasts)
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
                sr_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1).set_index(keys='figi')
                if not sr_last_signal.empty:
                    if (sr_last_signal.sell_flag[figi] != 1
                            and sr_last_signal.datetime[figi].date() != _now().date()
                            and df_shares.loc[df_shares.index == figi].short_enabled_flag[0]):
                        date = rsi.index[-1]
                        df_hist_sgnls = save_signal_to_df(buy_flag=0, sell_flag=1, last_price=last_price, figi=figi,
                                                          date=date, strategy='rsi', df_shares=df_shares,
                                                          df=df_hist_sgnls, rsi_float=rsi)
                        send_signal_to_strategy_subscribers(df=df_hist_sgnls)
                elif df_shares.loc[df_shares.index == figi].short_enabled_flag[0]:
                    date = rsi.index[-1]
                    df_hist_sgnls = save_signal_to_df(buy_flag=0, sell_flag=1, last_price=last_price, figi=figi,
                                                      date=date, strategy='rsi', df_shares=df_shares, df=df_hist_sgnls,
                                                      rsi_float=rsi)
                    send_signal_to_strategy_subscribers(df=df_hist_sgnls)

            if rsi[0] <= lower_rsi:  # если истина, записываем в DF сигнал на покупку
                sr_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1).set_index(keys='figi')
                if not sr_last_signal.empty:
                    if sr_last_signal.buy_flag.all() != 1\
                            and sr_last_signal.datetime[figi].date() != _now().date():
                        date = rsi.index[-1]
                        df_hist_sgnls = save_signal_to_df(buy_flag=1, sell_flag=0, last_price=last_price, figi=figi,
                                                          date=date, strategy='rsi', df_shares=df_shares,
                                                          df=df_hist_sgnls, rsi_float=rsi)
                        send_signal_to_strategy_subscribers(df=df_hist_sgnls)
                else:
                    date = rsi.index[-1]
                    df_hist_sgnls = save_signal_to_df(buy_flag=1, sell_flag=0, last_price=last_price, figi=figi,
                                                      date=date, strategy='rsi', df_shares=df_shares, df=df_hist_sgnls,
                                                      rsi_float=rsi)
                    send_signal_to_strategy_subscribers(df=df_hist_sgnls)

    df_hist_sgnls.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

    return df_hist_sgnls
