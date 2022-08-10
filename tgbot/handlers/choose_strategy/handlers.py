from telegram import Update
from telegram.ext import CallbackContext

from tgbot import static_text
from tgbot.models import User, Strategy
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_connect


def command_strategy(update: Update, context: CallbackContext) -> None:
    user = User.get_user(update, context)
    user.record_command(command_name="strategy")

    subscriptions = list(map(lambda item: item.strategy_id, user.user_subscriptions()))
    available_strategies = list(filter(lambda s: s.strategy_id not in subscriptions, Strategy.all()))

    if len(available_strategies) > 0:
        update.message.reply_text(
            static_text.add_new_strategy,
            reply_markup=make_keyboard_for_strategies_connect(available_strategies)
        )
    else:
        update.message.reply_text('✅Уже подключены все доступные стратегии')


