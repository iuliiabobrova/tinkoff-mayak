from pandas import DataFrame
from telegram import ParseMode, Bot, error

from dtb.settings import TELEGRAM_TOKEN

from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.models import User


async def send_signal_to_strategy_subscribers(df: DataFrame) -> None:

    signal = get_last_signals(df=df, amount=1)[0]
    strategy_id = signal.strategy_id

    users_with_strategy = await User.get_users_with_strategy_subscription(strategy_id=strategy_id)
    # TODO изменить в базе всех пользователей с подключенной sma на sma_50_200 и удалить if
    if strategy_id == 'sma_50_200':
        users_with_strategy += list(User.get_users_with_strategy_subscription(strategy_id='sma'))

    user_ids = [user.user_id for user in users_with_strategy]
    for user_id in user_ids:
        try:
            Bot(TELEGRAM_TOKEN).send_message(
                text=f"{signal}",
                chat_id=user_id,
                disable_web_page_preview=True,
                parse_mode=ParseMode.HTML,
                reply_markup=make_keyboard_for_signal(user_id=user_id, signal=signal)
            )
            await asyncio.sleep(0.04)
        except error.Unauthorized:
            success = False
        else:
            success = True

