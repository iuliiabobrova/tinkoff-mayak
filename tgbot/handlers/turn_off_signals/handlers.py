from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_disconnect
from tgbot.models import User, Command
from tgbot.handlers.turn_off_signals import static_text


def command_off(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    strategies = u.user_strategies()

    if len(strategies) == 1:
        u.unsubscribe_user_from_all_strategies()
        Command.record(command_name="off",
                       user_id=u.user_id, username=u.username)
        update.message.reply_text(static_text.off_signals)
    elif len(strategies) > 0:
        update.message.reply_text('Какую стратегию отключить?',
                                  reply_markup=make_keyboard_for_strategies_disconnect())
    else:
        update.message.reply_text(static_text.no_signals)
