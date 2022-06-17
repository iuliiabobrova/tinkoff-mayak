from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.turn_off_signals import static_text


def command_off(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(static_text.off_signals)
