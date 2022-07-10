from pandas import DataFrame, read_csv

from tinkoff.invest import Client

from corestrategy.settings import *
from corestrategy.utils import _now
from corestrategy.actual_data_download import get_all_lasts
from dtb.settings import INVEST_TOKEN


def calc_actual_signals_rsi(figi_list: list,
                            df_all_lasts: DataFrame,
                            df_close_prices: DataFrame):

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
            print(rsi)


df_close_prices = read_csv(filepath_or_buffer='../../csv/historic_close_prices.csv',
                           sep=';',
                           index_col=0,
                           parse_dates=[0],
                           dtype=float)
with Client(INVEST_TOKEN) as client:  # обёртка
    # запрашивает название всех акций и закладывает их в переменную
    all_shares = client.instruments.shares()
df_shares = DataFrame(data=all_shares.instruments)
df_shares.set_index(keys=['figi'], inplace=True)
figi_list = df_shares.index.tolist()

df_all_lasts = get_all_lasts(figi_list=['BBG000LWNRP3'])
calc_actual_signals_rsi(figi_list=figi_list,
                        df_all_lasts=df_all_lasts,
                        df_close_prices=df_close_prices)
