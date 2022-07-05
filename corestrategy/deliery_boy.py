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
