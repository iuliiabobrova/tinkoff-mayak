from telegram import Update
from telegram.ext import CallbackContext

from tgbot.models import User, Command


def command_stock(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="stock",
                   user_id=u.user_id, username=u.username)
