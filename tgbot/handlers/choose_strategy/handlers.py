from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.choose_strategy import static_text
from tgbot.models import User, Command
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_connect


def command_strategy(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="strategy",
                   user_id=u.user_id, username=u.username)
    update.message.reply_text(
        static_text.add_new_strategy, reply_markup=make_keyboard_for_strategies_connect())
