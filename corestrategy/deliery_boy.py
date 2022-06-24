from pandas import DataFrame
from time import sleep
from dtb.settings import TELEGRAM_TOKEN as tg_token
from datetime import datetime, timedelta
from typing import Tuple

from tgbot.models import User
from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.handlers.broadcast_message.utils import _send_message


def send_signal_to_strategy_subscribers(df: DataFrame, size_of_df_change: int) -> None:
    signals = get_last_signals(df=df, amount=size_of_df_change)
    for signal in signals:
        strategy_id = signal.strategy_id
        users_with_strategy = User.get_users_with_strategy_subscription(strategy_id=strategy_id)
        for user in users_with_strategy:
            _send_message(text=f"{signal}",
                          user_id=user.user_id,
                          tg_token=tg_token,
                          disable_web_page_preview=True,
                          reply_markup=make_keyboard_for_signal(user.user_id, signal))
            sleep(0.4)

    print("Signals sent!")


# TODO можно рассылать сообщение через эту штуку через
# telegram api https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions-–-JobQueue
# чтобы не делать бесконечный цикл и sleep
def run_delivery_boy(df_rsi: DataFrame,
                     df_sma: DataFrame,
                     previous_size_df_sma: int,
                     previous_size_df_rsi: int) -> Tuple[int, int]:

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

    return previous_size_df_sma, previous_size_df_rsi
