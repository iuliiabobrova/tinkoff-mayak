from datetime import datetime, timedelta
from threading import Event

from pandas import DataFrame
from tinkoff.invest import Client

from dtb.settings import INVEST_TOKEN
from corestrategy.utils import now_msk


def last_is_actual(last_price) -> bool:
    _now_ = now_msk() - timedelta(hours=3)
    a = _now_.year == last_price.time.year
    b = _now_.month == last_price.time.month
    c = _now_.day == last_price.time.day
    d = _now_.hour == last_price.time.hour
    e = _now_.minute == last_price.time.minute
    f = _now_.minute - 1 == last_price.time.minute
    g = _now_.minute - 2 == last_price.time.minute
    h = e or f or g

    return a and b and c and d and h


def get_all_lasts(figi_list: list) -> DataFrame:
    """Получаем самые последние цены всех акций"""

    try:
        with Client(INVEST_TOKEN) as client:
            request_lasts = client.market_data.get_last_prices(figi=figi_list).last_prices  # запрос ластов из API

        df = DataFrame(columns=['figi', 'last_price', 'datetime'])
        for n in request_lasts:
            if last_is_actual(last_price=n):
                date_time = datetime(n.time.year, n.time.month, n.time.day, n.time.hour, n.time.minute, n.time.second)

                if n.price.nano == 0:
                    last_price = n.price.units
                else:
                    last_price = round(n.price.units + (n.price.nano / 1_000_000_000), 6)

                figi = n.figi  # получает figi из ответа API
                df.loc[len(df.index)] = [figi, last_price, date_time]  # сохраняем данные в DF
        df.set_index('figi', inplace=True)  # индексируем DF по figi
    except Exception as e:
        print(e)
        Event().wait(60)
        df = get_all_lasts(figi_list)
        print('lasts are successfully downloaded')

    return df
