from pandas import DataFrame
from time import sleep
from typing import Union, Optional, Dict, List

from telegram import ParseMode, MessageEntity, Bot, error

from dtb.settings import TELEGRAM_TOKEN
from dtb.celery import app

from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.models import User
from corestrategy.utils import _now


def _send_message(
    user_id: Union[str, int],
    text: str,
    parse_mode: Optional[str] = ParseMode.HTML,
    reply_markup: Optional[List[List[Dict]]] = None,
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: Optional[bool] = None,
    entities: Optional[List[MessageEntity]] = None,
    tg_token: str = TELEGRAM_TOKEN,
) -> bool:
    bot = Bot(tg_token)
    try:
        m = bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview,
            entities=entities,
        )
    except error.Unauthorized:
        User.objects.filter(user_id=user_id).update(is_blocked_bot=True)
        success = False
    else:
        success = True
        User.objects.filter(user_id=user_id).update(is_blocked_bot=False)
    return success


@app.task(ignore_result=True)
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

    print(f"Signals sent! Now-time: {_now()}")
