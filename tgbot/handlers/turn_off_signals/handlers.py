from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_disconnect
from tgbot.handlers.turn_off_signals.static_text import what_to_disconnect
from tgbot.models import User, Command
from tgbot.handlers.turn_off_signals import static_text


def command_off(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    strategies = list(map(lambda item: item.strategy_id, u.user_subscriptions()))

    Command.record(command_name="off",
                   user_id=u.user_id, username=u.username)

    if len(strategies) == 1:
        u.unsubscribe_user_from_all_strategies()
        update.message.reply_text(static_text.off_signals)
    elif len(strategies) > 0:
        update.message.reply_text(what_to_disconnect,
                                  reply_markup=make_keyboard_for_strategies_disconnect(strategies))
    else:
        update.message.reply_text(static_text.no_signals)
