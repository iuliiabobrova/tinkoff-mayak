from datetime import datetime
from pandas import DataFrame

from tinkoff.invest import Client

from dtb.settings import INVEST_TOKEN


def get_all_lasts(figi_list: list) -> DataFrame:
    """Получаем самые последние цены всех акций"""
    # TODO исключить уточняющие свечи?

    with Client(INVEST_TOKEN) as client:
        request_lasts = client.market_data.get_last_prices(figi=figi_list).last_prices  # запрос ластов из API

    df = DataFrame(columns=['figi', 'last_price', 'datetime'])
    for n in request_lasts:
        # парсит last из ответа API
        last_price = f"{n.price.units}.{n.price.nano // 10000000}"
        date_time = datetime(n.time.year, n.time.month, n.time.day, n.time.hour, n.time.minute, n.time.second)
        figi = n.figi  # получает figi из ответа API
        df.loc[len(df.index)] = [figi, last_price, date_time]  # сохраняем данные в DF
    df.set_index('figi', inplace=True)  # индексируем DF по figi

    return df
