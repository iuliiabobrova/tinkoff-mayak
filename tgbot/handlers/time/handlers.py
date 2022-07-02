from telegram import Update
from telegram.ext import CallbackContext

from tgbot.models import User, Command


def command_time(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="time",
                   user_id=u.user_id, username=u.username)
