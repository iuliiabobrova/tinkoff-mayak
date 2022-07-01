from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.choose_strategy import static_text
from tgbot.models import User
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies


def command_strategy(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    u.record_command_event("strategy")
    update.message.reply_text(
        static_text.add_new_strategy, reply_markup=make_keyboard_for_strategies())
