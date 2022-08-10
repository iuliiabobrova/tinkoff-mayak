from pandas import DataFrame
from numpy import nanpercentile
from typing import List

from corestrategy.settings import *
from corestrategy.utils import save_signal_to_df, now_msk


def calc_actual_signals_rsi(df_shares: DataFrame,
                            df_hist_sgnls: DataFrame,
                            df_all_lasts: DataFrame,
                            df_close_prices: DataFrame,
                            df_actual_signals: DataFrame,
                            df_rsi: DataFrame) -> List:  # TODO использовать заранее рассчитанные показатели RSI
    """Функция позволяет рассчитать индикатор RSI и актуальные сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    upper_rsi = upper_rsi_fix
    lower_rsi = lower_rsi_fix
    figi_with_data_list = df_close_prices.columns

    if not df_all_lasts.empty:
        for figi in df_all_lasts.index:

            if any([x == figi for x in figi_with_data_list]):
                sr_close_prices = df_close_prices[f'{figi}'].dropna()[-1:-365:-1][::-1]
                if len(sr_close_prices) > 12:
                    last_price = df_all_lasts.loc[figi].last_price
                    sr_close_prices.loc[now_msk()] = last_price

                    # расчет по формуле RSI
                    sr_delta = sr_close_prices.diff()
                    sr_up = sr_delta.clip(lower=0)
                    sr_down = -1 * sr_delta.clip(upper=0)
                    sr_ema_up = sr_up.ewm(com=period_of_ema, adjust=False).mean().tail(1)
                    sr_ema_down = sr_down.ewm(com=period_of_ema, adjust=False).mean().tail(1)
                    sr_rs = sr_ema_up / sr_ema_down
                    sr_rsi = (100 - (100 / (1 + sr_rs))).round(4)

                    # определение границ нормы RSI (если включено в настройках)
                    if settings_percentile:
                        upper_rsi = nanpercentile(sr_rsi,
                                                  upper_rsi_percentile)  # верхняя граница RSI, выше 5% высоких RSI
                        lower_rsi = nanpercentile(sr_rsi,
                                                  lower_rsi_percentile)  # нижняя граница RSI, ниже лишь 2.5% низких RSI

                    rsi = sr_rsi[0]
                    if rsi >= upper_rsi or rsi <= lower_rsi:  # если истина, записываем в DF сигнал
                        buy_flag = 0 if rsi >= upper_rsi else 1
                        date = now_msk()
                        short_enabled = df_shares.loc[df_shares.index == figi].short_enabled_flag[0]
                        sr_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1).set_index(keys='figi')
                        if not sr_last_signal.empty:
                            if sr_last_signal.datetime[figi].date() != now_msk().date():
                                if buy_flag == 0 and short_enabled:
                                    [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag,
                                                                                           last_price=last_price,
                                                                                           figi=figi, date_time=date,
                                                                                           strategy_id='rsi',
                                                                                           df_shares=df_shares,
                                                                                           df=df_hist_sgnls,
                                                                                           df_actual_signals=df_actual_signals,
                                                                                           rsi_float=rsi)
                                    df_hist_sgnls.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

                                elif buy_flag == 1:
                                    [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag,
                                                                                       last_price=last_price, figi=figi,
                                                                                       date_time=date,
                                                                                       strategy_id='rsi',
                                                                                       df_shares=df_shares,
                                                                                       df=df_hist_sgnls,
                                                                                       df_actual_signals=df_actual_signals,
                                                                                       rsi_float=rsi)
                                    df_hist_sgnls.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

                            elif sr_last_signal.buy_flag[0] != buy_flag:
                                [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag,
                                                                                   last_price=last_price, figi=figi,
                                                                                   date_time=date, strategy_id='rsi',
                                                                                   df_shares=df_shares,
                                                                                   df=df_hist_sgnls, df_actual_signals=df_actual_signals,
                                                                                   rsi_float=rsi)
                                df_hist_sgnls.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

                        else:
                            [df_hist_sgnls, df_actual_signals] = save_signal_to_df(buy_flag=buy_flag, last_price=last_price,
                                                                               figi=figi, date_time=date,
                                                                               strategy_id='rsi', df_shares=df_shares,
                                                                               df=df_hist_sgnls, df_actual_signals=df_actual_signals,
                                                                               rsi_float=rsi)
                            df_hist_sgnls.to_csv(path_or_buf='csv/historic_signals_rsi.csv', sep=';')

    return [df_hist_sgnls, df_actual_signals]
