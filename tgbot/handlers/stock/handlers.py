from telegram import Update
from telegram.ext import CallbackContext

from tgbot.models import User, Command


def command_stock(update: Update, context: CallbackContext) -> None:
    user = User.get_user(update, context)
    user.record_command(command_name="stock")
