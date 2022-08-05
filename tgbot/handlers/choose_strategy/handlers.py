from telegram import Update
from telegram.ext import CallbackContext

from tgbot import static_text
from tgbot.models import User, Command
from corestrategy.utils import Strategy
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_connect


def command_strategy(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="strategy", user_id=u.user_id, username=u.username)

    subscriptions = list(map(lambda item: item.strategy_id, u.user_subscriptions()))
    available_strategies = list(filter(lambda s: s.strategy_id not in subscriptions, Strategy.all()))

    if len(available_strategies) > 0:
        update.message.reply_text(
            static_text.add_new_strategy,
            reply_markup=make_keyboard_for_strategies_connect(available_strategies)
        )
    else:
        update.message.reply_text('✅Уже подключены все доступные стратегии')


