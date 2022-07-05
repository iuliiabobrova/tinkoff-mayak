from pandas import DataFrame
from time import sleep
from datetime import datetime, timedelta
from typing import List

from tgbot.models import User
from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.handlers.broadcast_message.utils import _send_message


def send_signal_to_strategy_subscribers(df: DataFrame) -> None:

    signals = get_last_signals(df=df, amount=1)
    for signal in signals:
        strategy_id = signal.strategy_id
        users_with_strategy = User.get_users_with_strategy_subscription(strategy_id=strategy_id)
        for user in users_with_strategy:
            _send_message(text=f"{signal}",
                          user_id=user.user_id,
                          disable_web_page_preview=True,
                          reply_markup=make_keyboard_for_signal(user.user_id, signal))
            sleep(0.4)

    print("Signals sent!")


def run_delivery_boy(df_sma: DataFrame,
                     df_rsi: DataFrame,
                     previous_size_df_sma: int,
                     previous_size_df_rsi: int) -> List[int]:
    """Проверяет, увеличился ли DataFrame с актуальными сигналами. Если да, высылает сигналы"""

    size_df_sma = df_sma.index.max()
    size_df_rsi = df_rsi.index.max()

    if size_df_sma > previous_size_df_sma:
        size_of_df_change = size_df_sma - previous_size_df_sma
        print(f'trying to send {size_of_df_change} signals:', datetime.now() + timedelta(hours=3))
        send_signal_to_strategy_subscribers(df=df_sma, size_of_df_change=size_of_df_change)

    if size_df_rsi > previous_size_df_rsi:
        size_of_df_change = size_df_rsi - previous_size_df_rsi
        print(f'trying to send {size_of_df_change} signals:', datetime.now() + timedelta(hours=3))
        send_signal_to_strategy_subscribers(df=df_rsi, size_of_df_change=size_of_df_change)

    previous_size_df_sma = size_df_sma
    previous_size_df_rsi = size_df_rsi

    return [previous_size_df_sma, previous_size_df_rsi]
