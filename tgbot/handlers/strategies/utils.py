from typing import List
from pandas import DataFrame, to_datetime
from datetime import time, datetime, timedelta

from tgbot.handlers.strategies.static_text import buy_signal, sell_signal, rsi_high, rsi_low, sma_high, sma_low


class Signal:
    def __init__(self, **kwargs):
        self.figi = kwargs['figi']
        self.ticker = kwargs['ticker']
        self.share_name = kwargs['share_name']
        self.datetime = kwargs['datetime']
        self.last_price = kwargs['last_price']
        self.sell_flag = kwargs['sell_flag']
        self.buy_flag = kwargs['buy_flag']
        self.strategy_id = kwargs['strategy_id']
        self.profit = kwargs['profit']
        self.currency = kwargs['currency']

    def __str__(self) -> str:
        signal = buy_signal if self.buy_flag == 1 else sell_signal
        date = to_datetime(self.datetime, dayfirst=True) + timedelta(hours=3)
        if date - timedelta(hours=3) == time(hour=0, minute=0, second=0):
            date = date.date()
        else:
            date = datetime.strftime(date, format='%d-%m-%Y %Hч:%Mм')

        if self.strategy_id == 'sma':
            description = sma_high if self.buy_flag == 1 else sma_low
        elif self.strategy_id == 'rsi':
            description = rsi_low if self.buy_flag == 1 else rsi_high

        return f"{signal}\n" \
            f"{self.share_name} (${self.ticker}) {self.last_price} {self.currency}\n" \
            f"{description}\n" \
            f"🕓{date}"

    def get_url(self, user_id) -> str:
        return f"http://www.tinkoff.ru/invest/stocks/{self.ticker}?utm_source=mayak_bot&utm_content={user_id}"


def get_last_signals(df: DataFrame, amount: int) -> List[Signal]:
    signals = df.tail(amount).to_dict('records')

    return list(map(lambda x: Signal(**x), signals))


def get_last_signal(df: DataFrame) -> Signal:
    signals = get_last_signals(df, n=1)

    return signals[0]
