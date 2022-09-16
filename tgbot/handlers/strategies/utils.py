from typing import List
from pandas import DataFrame, to_datetime
from datetime import time, datetime

from tgbot.static_text import (
    buy_signal, sell_signal, rsi_high, rsi_low,
    sma_50_200_high, sma_50_200_low, sma_30_90_low,
    sma_20_60_low, sma_30_90_high, sma_20_60_high
)


class Signal:
    def __init__(self, **kwargs):
        self.figi = kwargs['figi']
        self.ticker = kwargs['ticker']
        self.share_name = kwargs['share_name']
        self.datetime = kwargs['datetime']
        self.last_price = kwargs['last_price']
        self.buy_flag = kwargs['buy_flag']
        self.strategy_id = kwargs['strategy_id']
        self.profit = kwargs['profit']
        self.currency = kwargs['currency']
        if self.currency=='usd':
            self.currency = '$'
        elif self.currency=='eur':
            self.currency = '€'
        elif self.currency=='rub':
            self.currency = '₽'
        try:
            self.last_price = round(self.last_price,2)
        except:
            pass

    def __str__(self) -> str:
        signal = buy_signal if self.buy_flag == 1 else sell_signal
        date = to_datetime(self.datetime, dayfirst=True)
        if date.time() == time():
            date = date.date()
        else:
            date = datetime.strftime(date, format='%d-%m-%Y %H:%M(MSK)')

        if self.strategy_id.startswith('sma_50_200'):
            description = sma_50_200_high if self.buy_flag == 1 else sma_50_200_low
        elif self.strategy_id.startswith('sma_30_90'):
            description = sma_30_90_high if self.buy_flag == 1 else sma_30_90_low
        elif self.strategy_id.startswith('sma_20_60'):
            description = sma_20_60_high if self.buy_flag == 1 else sma_20_60_low
        elif self.strategy_id.startswith('rsi'):
            description = rsi_low if self.buy_flag == 1 else rsi_high
        else:
            description = self.strategy_id  # TODO убрать else description = self.strategy_id

        return f"{signal}\n" \
            f"{self.share_name}(<b>{self.ticker}</b>) {self.last_price}<b>{self.currency}</b>\n" \
            f"{description}\n" \
            f"🕓{date}"

    def get_url(self, user_id) -> str:
        return f"https://www.tinkoff.ru/invest/stocks/{self.ticker}?utm_source=mayak_bot&utm_content={user_id}"


def get_last_signals(df: DataFrame, amount: int) -> List[Signal]:
    signals = df.tail(amount).to_dict('records')

    return list(map(lambda x: Signal(**x), signals))


def get_last_signal(df: DataFrame) -> Signal:
    signals = get_last_signals(df, amount=1)

    return signals[0]
