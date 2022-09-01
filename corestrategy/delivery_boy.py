import asyncio
from queue import Queue
from threading import Thread

from telegram import ParseMode, Bot, error
from pandas import DataFrame

from corestrategy.utils import now_msk, Limit
from dtb.settings import TELEGRAM_TOKEN

from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.models import User
from tgbot.handlers.strategies.utils import Signal


async def send_signal_to_one_subscriber(signal: DataFrame):

    @Limit(calls=25, period=1)
    async def _send_message():
        try:
            Bot(TELEGRAM_TOKEN).send_message(
                text=f"{signal}",
                chat_id=user_id,
                disable_web_page_preview=True,
                parse_mode=ParseMode.HTML,
                reply_markup=make_keyboard_for_signal(user_id=user_id, signal=signal),
                timeout=3
            )
        except error.Unauthorized:
            print(f'error when sending signal to user: {user_id}         {now_msk()}')
            print(f'user {user_id} is blocked, error refused')
            User.objects.filter(user_id=user_id).update(is_blocked_bot=True)
        except error.RetryAfter(10):
            print(f'ATTENTION! Too fast message sending')
            print(f'sleeping 10 seconds')
        except Exception as e:
            print(f'error when sending signal to user: {e}         {now_msk()}')

    strategy_id = signal.strategy_id
    users_with_strategy = await User.get_users_with_strategy_subscription(strategy_id=strategy_id)
    # TODO изменить в базе всех пользователей с подключенной sma на sma_50_200 и удалить if
    if strategy_id == 'sma_50_200':
        users_with_strategy += await User.get_users_with_strategy_subscription(strategy_id='sma')
    user_ids = [user.user_id for user in users_with_strategy]
    for user_id in user_ids:
        await _send_message()


def send_signal_to_strategy_subscribers(q: Queue) -> None:
    print('thread starts')  # TODO del
    signal = q.get()
    print(signal)  # TODO del
    send_signal_to_one_subscriber(signal=signal)
    asyncio.sleep(10)  # TODO del
    print('thread is ended')  # TODO del
    q.task_done()


def run_delivery_boy(df: DataFrame, q: Queue) -> Queue:
    signals = list(map(lambda x: Signal(**x), df.to_dict('records')))
    if len(signals) != 0:
        for signal in signals:
            print(signal)  # TODO del
            q.put(signal)
        # создаём и запускаем потоки  # TODO del
        thread2 = Thread(target=send_signal_to_strategy_subscribers, args=(q,))
        thread2.start()
        # Блокируем дальнейшее выполнение до завершения всех заданий  # TODO del
        q.join()

    return q
