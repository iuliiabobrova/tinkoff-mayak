from telegram import Update
from telegram.ext import CallbackContext

from tgbot.models import User, Command
from tgbot.handlers.turn_off_signals import static_text


def command_off(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    unsubscribed = u.unsubscribe_user_from_strategies()
    Command.record(command_name="off",
                   user_id=u.user_id, username=u.username)

    if unsubscribed:
        update.message.reply_text(static_text.off_signals)
    else:
        update.message.reply_text(static_text.no_signals)
