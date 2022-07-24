from pandas import read_csv
from telegram import ParseMode, Update
from telegram.ext import CallbackContext
from time import sleep

from tgbot.models import User, Command, Strategy
from tgbot.handlers.strategies import static_text
from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal


def strategy_connect(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    strategy = Strategy(strategy_id=query.data)

    u = User.get_user(update, context)
    subscribed = u.subscribe_user_to_strategy(strategy_id=strategy.strategy_id)

    Command.record(command_name=strategy.strategy_id, user_id=u.user_id, username=u.username)
    query.answer()

    if subscribed:
        query.edit_message_text(
            text=strategy.description(), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

        sleep(4)

        signals_df = read_csv('csv/historic_signals_%s.csv' % strategy.strategy_id,
                              sep=';', index_col=0, parse_dates=['datetime'], low_memory=False)
        signals = get_last_signals(df=signals_df, amount=3)

        for signal in signals:
            query.message.reply_html(
                text=f"{signal}", reply_markup=make_keyboard_for_signal(u.user_id, signal))

    else:
        query.edit_message_text(text=static_text.already_subscribed)
