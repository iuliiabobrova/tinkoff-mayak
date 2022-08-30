from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.turn_off_signals.keyboards import make_keyboard_for_strategies_disconnect
from tgbot.static_text import (
    what_to_disconnect, no_subscriptions_to_strategy, strategy_off_signals
)
from tgbot.models import User, Command, Strategy
from tgbot import static_text


def command_off(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    subscriptions = list(map(lambda item: item.strategy_id, u.user_subscriptions()))
    strategies = list(filter(lambda s: s.strategy_id in subscriptions, Strategy.all()))

    if len(strategies) == 1:
        u.unsubscribe_user_from_all_strategies()
        update.message.reply_text(static_text.off_signals)
    elif len(strategies) > 0:
        update.message.reply_text(
            what_to_disconnect,
            reply_markup=make_keyboard_for_strategies_disconnect(strategies)
        )
    else:
        update.message.reply_text(static_text.no_signals)


def strategy_disconnect(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    strategy = Strategy(strategy_id=query.data.replace('_disconnect', ''))

    u = User.get_user(update, context)
    unsubscribed = u.unsubscribe_user_from_strategy(strategy_id=strategy.strategy_id)

    query.answer()

    if unsubscribed:
        Command.record(command_name=f'OFF {strategy.strategy_name}', user_id=u.user_id, username=u.username)
        message_text = strategy_off_signals(strategy.strategy_name)
        query.edit_message_text(text=message_text)
    else:
        query.edit_message_text(text=no_subscriptions_to_strategy)


def all_disconnect(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    u.unsubscribe_user_from_all_strategies()

    query = update.callback_query
    query.answer()

    query.edit_message_text(text=static_text.off_signals)


def chat_member_update_received(update: Update, context: CallbackContext):
    update = update['my_chat_member']['new_chat_member']
    user_id = update['user']['id']
    if update['status'] == 'kicked':
        User.objects.filter(user_id=user_id).update(is_blocked_bot=True)
    elif update['status'] == 'member':
        User.objects.filter(user_id=user_id).update(is_blocked_bot=False)
