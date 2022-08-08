from pandas import DataFrame, read_csv
from numpy import nanpercentile

from tinkoff.invest import Client

from corestrategy.settings import *
from corestrategy.utils import _msknow
from corestrategy.actual_data_download import get_all_lasts

from dtb.settings import INVEST_TOKEN


def _calc_actual_signals_rsi(df_shares: DataFrame,
                             df_hist_sgnls: DataFrame,
                             df_all_lasts: DataFrame,
                             df_close_prices: DataFrame,
                             df_rsi: DataFrame = None) -> DataFrame:
    """Функция позволяет рассчитать индикатор RSI и актуальные сигналы на основе индикатора.
    Триггером являются самые низкие и самые высокие значения RSI, области которых обозначены в
    переменных upper_rsi_percentile, lower_rsi_percentile"""

    upper_rsi = upper_rsi_fix
    lower_rsi = lower_rsi_fix
    figi_with_data_list = df_close_prices.columns

    if not df_all_lasts.empty:
        #print('df_all_lasts is not empty:', not df_all_lasts.empty)
        for figi in df_all_lasts.index:

            if any([x == figi for x in figi_with_data_list]):
                #print('figi from df_all_lasts is in df_close_prices')
                sr_close_prices = df_close_prices[f'{figi}'].dropna()[-1:-365:-1][::-1]
                if len(sr_close_prices) > 12:
                    print('enough close prices to calc')
                    last_price = df_all_lasts.loc[figi].last_price
                    sr_close_prices.loc[_msknow()] = last_price

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
                    print(figi, rsi)
                    if rsi >= upper_rsi or rsi <= lower_rsi:  # если истина, записываем в DF сигнал
                        print('Potential signal')
                        buy_flag = 0 if rsi >= upper_rsi else 1
                        short_enabled = df_shares.loc[df_shares.index == figi].short_enabled_flag[0]
                        sr_last_signal = df_hist_sgnls[df_hist_sgnls.figi == figi].tail(1).set_index(keys='figi')
                        if not sr_last_signal.empty:
                            print('SR is not empty')
                            if sr_last_signal.datetime[figi].date() != _msknow().date():
                                print('Datetime of sr is ok')
                                if buy_flag == 0 and short_enabled:
                                    print('Signal:', "sell" if buy_flag == 0 else 'buy', figi)
                                elif buy_flag == 1:
                                    print('Signal:', "sell" if buy_flag == 0 else 'buy', figi)

                            elif sr_last_signal.buy_flag != buy_flag:
                                print('Date isnt ok, but signal is')
                                print('Signal:', "sell" if buy_flag == 0 else 'buy', figi)

                        else:
                            print('Signal:', "sell" if buy_flag == 0 else 'buy', figi)

    return df_hist_sgnls


if __name__ == "__main__":
    df_close_prices = read_csv(
        filepath_or_buffer='../../csv/historic_close_prices.csv',
        sep=';',
        index_col=0,
        parse_dates=[0],
        dtype=float
    )
    df_hist_sgnls = read_csv(
        filepath_or_buffer='../../csv/historic_signals_rsi.csv',
        sep=';',
        index_col=0,
        parse_dates=['datetime'],
        low_memory=False
    )
    with Client(INVEST_TOKEN) as client:  # обёртка
        # запрашивает название всех акций и закладывает их в переменную
        all_shares = client.instruments.shares()
    df_shares = DataFrame(data=all_shares.instruments)
    df_shares.set_index(keys=['figi'], inplace=True)
    figi_list = df_shares.index.tolist()

    n = 0
    while True:
        n += 1
        print('try number', n)
        df_all_lasts = get_all_lasts(figi_list=figi_list)
        _calc_actual_signals_rsi(
            df_hist_sgnls=df_hist_sgnls,
            df_all_lasts=df_all_lasts,
            df_close_prices=df_close_prices,
            df_shares=df_shares
        )

