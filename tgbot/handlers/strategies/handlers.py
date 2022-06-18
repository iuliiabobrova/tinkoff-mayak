from pandas import read_csv
from telegram import ParseMode, Update
from telegram.ext import CallbackContext
from time import sleep

from tgbot.models import User, UserSubscription
from tgbot.handlers.strategies import static_text
from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal


def sma(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    subscribed = UserSubscription.subscribe_user_to_strategy(
        user=u, strategy_id="sma")

    query = update.callback_query
    query.answer()

    if subscribed:
        query.edit_message_text(
            text=static_text.sma_is_chosen, parse_mode=ParseMode.HTML)

        sleep(5)

        signals_df = read_csv('csv/historic_signals_sma.csv', sep=';')
        signals = get_last_signals(df=signals_df, n=3)

        for signal in signals:
            query.message.reply_html(
                text=f"{signal}", reply_markup=make_keyboard_for_signal(u.user_id, signal))

    else:
        query.edit_message_text(text=static_text.already_subscribed)


def rsi(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    subscribed = UserSubscription.subscribe_user_to_strategy(
        user=u, strategy_id="rsi")

    query = update.callback_query
    query.answer()

    if subscribed:
        query.edit_message_text(
            text=static_text.rsi_is_chosen, parse_mode=ParseMode.HTML)

        sleep(5)

        signals_df = read_csv('csv/historic_signals_rsi.csv', sep=';')
        signals = get_last_signals(df=signals_df, n=3)

        for signal in signals:
            query.message.reply_html(
                text=f"{signal}", reply_markup=make_keyboard_for_signal(u.user_id, signal))

    else:
        query.edit_message_text(text=static_text.already_subscribed)
