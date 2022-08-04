from queue import Queue
from typing import Union, Optional, Dict, List
from threading import Thread, Event

from telegram import ParseMode, MessageEntity, Bot, error
from pandas import DataFrame

from dtb.settings import TELEGRAM_TOKEN

from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.models import User
from tgbot.handlers.strategies.utils import Signal


def _send_message(
    user_id: Union[str, int],
    text: str,
    parse_mode: Optional[str] = ParseMode.HTML,
    reply_markup: Optional[List[List[Dict]]] = None,
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: Optional[bool] = None,
    entities: Optional[List[MessageEntity]] = None,
    tg_token: str = TELEGRAM_TOKEN,
) -> None:

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
        pass
    else:
        pass


def send_signal_to_one_subscriber(signal: DataFrame) -> None:

    strategy_id = signal.strategy_id
    users_with_strategy = list(User.get_users_with_strategy_subscription(strategy_id=strategy_id))
    # TODO изменить в базе всех пользователей с подключенной sma на sma_50_200 и удалить if
    if strategy_id == 'sma_50_200':
        users_with_strategy += list(User.get_users_with_strategy_subscription(strategy_id='sma'))
    for user in users_with_strategy:
        _send_message(text=f"{signal}",
                      user_id=user.user_id,
                      disable_web_page_preview=True,
                      reply_markup=make_keyboard_for_signal(user.user_id, signal))
        Event().wait(timeout=0.04)  # TG позволяет боту отправлять не более 1800 сообщений в минуту


def send_signal_to_strategy_subscribers(q: Queue) -> None:

    signal = q.get()
    print(signal)
    send_signal_to_one_subscriber(signal=signal)
    q.task_done()


def run_delivery_boy(df: DataFrame, q: Queue) -> Queue:
    signals = list(map(lambda x: Signal(**x), df.to_dict('records')))
    if len(signals) != 0:
        for signal in signals:
            print(signal)
            q.put(signal)
        # создаём и запускаем потоки
        thread2 = Thread(target=send_signal_to_strategy_subscribers, args=(q,))
        thread2.start()
        # Блокируем дальнейшее выполнение до завершения всех заданий
        q.join()

    return q
