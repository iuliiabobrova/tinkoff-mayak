from pandas import read_csv
from telegram import ParseMode, Update
from telegram.ext import CallbackContext
from time import sleep

from tgbot.handlers.turn_off_signals.static_text import sma_off_signals, rsi_off_signals, no_subscriptions_to_strategy
from tgbot.models import User, Command
from tgbot.handlers.strategies import static_text
from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal


def strategy_connect(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    strategy_id = query.data
    components = strategy_id.split(sep='_')
    short_sma, long_sma = components[1], components[2]

    u = User.get_user(update, context)
    subscribed = u.subscribe_user_to_strategy(strategy_id=strategy_id)

    Command.record(command_name=query.data,
                   user_id=u.user_id, username=u.username)

    query.answer()

    if subscribed:
        query.edit_message_text(
            text=static_text.sma_is_chosen, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

        sleep(7)

        signals_df = read_csv('csv/historic_signals_sma_%i_%i.csv' % (short_sma, long_sma),
                              sep=';', index_col=0, parse_dates=['datetime'], low_memory=False)
        signals = get_last_signals(df=signals_df, amount=3)

        for signal in signals:
            query.message.reply_html(
                text=f"{signal}", reply_markup=make_keyboard_for_signal(u.user_id, signal))

    else:
        query.edit_message_text(text=static_text.already_subscribed)


def rsi_connect(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    subscribed = u.subscribe_user_to_strategy(strategy_id="rsi")
    Command.record(command_name="rsi",
                   user_id=u.user_id, username=u.username)

    query = update.callback_query
    query.answer()

    if subscribed:
        query.edit_message_text(
            text=static_text.rsi_is_chosen, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

        sleep(7)

        signals_df = read_csv('csv/historic_signals_rsi.csv',
                              sep=';', index_col=0, parse_dates=['datetime'], low_memory=False)
        signals = get_last_signals(df=signals_df, amount=3)

        for signal in signals:
            query.message.reply_html(
                text=f"{signal}", reply_markup=make_keyboard_for_signal(u.user_id, signal))

    else:
        query.edit_message_text(text=static_text.already_subscribed)
