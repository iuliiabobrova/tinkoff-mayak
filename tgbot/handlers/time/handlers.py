from telegram import Update
from telegram.ext import CallbackContext

from tgbot.models import User


def command_time(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    u.record_command_event("time")
    pass
