from datetime import datetime as dt
from time import sleep

from pandas import DataFrame
from tinkoff.invest import Client

from dtb.settings import INVEST_TOKEN
from corestrategy.historic_data_download import get_shares_list_to_csv


def _get_n_digits(number):
    s = str(number)
    if '.' in s:
        return abs(s.find('.') - len(s)) - 1
    else:
        return 0


# используется в df1
def _convert_stringprice_into_int_or_float(price: str) -> float or int:
    ndigits = _get_n_digits(price)
    if float(price) // 1 == float(price):
        price = int(float(price))
    else:
        price = round(float(price), ndigits)
    return price


def _get_all_lasts(figi_list: list):
    """Получаем самые последние цены всех акций"""

    with Client(INVEST_TOKEN) as client:
        request_lasts = client.market_data.get_last_prices(figi=figi_list).last_prices  # запрос ластов из API

    # подготовка df c float и int по last_price
    df_1 = DataFrame(columns=['figi', 'last_price', 'datetime'])
    for n in request_lasts:
        datetime = dt(n.time.year, n.time.month, n.time.day, n.time.hour, n.time.minute, n.time.second)
        last_price = f'{n.price.units}.{n.price.nano}'  # парсим last_price из ответа API
        last_price = _convert_stringprice_into_int_or_float(price=last_price)
        figi = n.figi  # получает figi из ответа API
        df_1.loc[len(df_1.index)] = [figi, last_price, datetime]  # сохраняем данные в DF
    df_1.set_index('figi', inplace=True)  # индексируем DF по figi

    # подготовка df с чистыми данными API
    df_2 = DataFrame(columns=['figi', 'units', 'nano', 'datetime'])
    for y in request_lasts:
        datetime = dt(y.time.year, y.time.month, y.time.day, y.time.hour, y.time.minute, y.time.second)
        figi = y.figi  # получает figi из ответа API
        df_2.loc[len(df_2.index)] = [figi, y.price.units, y.price.nano, datetime]  # сохраняем данные в DF

    return df_1, df_2


if __name__ == "__main__":

    while True:
        with Client(INVEST_TOKEN) as client:  # обёртка
            # запрашивает название всех акций и закладывает их в переменную
            all_shares = client.instruments.shares()
        df_shares = DataFrame(data=all_shares.instruments)
        df_shares.set_index(keys=['figi'], inplace=True)
        figi_list = df_shares.index.tolist()

        # подготовка df как в проекте
        df_list = _get_all_lasts(figi_list=figi_list)
        df1 = df_list[0].reset_index()
        df2 = df_list[1]
        n = 0

        for x in range(len(df1)):
            if len(str(df2.loc[df2.index[x]].nano)) == 1:
                delimetr = 1
            elif len(str(df2.loc[df2.index[x]].nano)) == 9:
                delimetr = 1_000_000_000
            elif len(str(df2.loc[df2.index[x]].nano)) == 8:
                delimetr = 100_000_000
            elif len(str(df2.loc[df2.index[x]].nano)) == 7:
                delimetr = 10_000_000
            elif len(str(df2.loc[df2.index[x]].nano)) == 6:
                delimetr = 1_000_000
            else:
                print('nano:', df2.loc[df2.index[x]].nano)
                print('len:', len(str(df2.loc[df2.index[x]].nano)))
                raise ValueError

            last_old = df1.loc[df1.index[x]].last_price
            last_new = (df2.loc[df2.index[x]].units + (df2.loc[df2.index[x]].nano / delimetr)).round(6)
            if last_new != last_old:
                print('df1:', last_old)
                print('df2:', last_new)
                print('df2 units-nano', df2.loc[df2.index[x]].units, df2.loc[df2.index[x]].nano)
                n += 1
        print('errors:', n)
        sleep(5)
