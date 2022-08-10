from pandas import read_csv
from telegram import ParseMode, Update
from telegram.ext import CallbackContext
from time import sleep

from tgbot.models import User, Command
from tgbot import static_text
from tgbot.handlers.strategies.utils import get_last_signals
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.models import Strategy


def strategy_connect(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    strategy = Strategy(strategy_id=query.data.replace('_connect', ''))

    user = User.get_user(update, context)
    subscribed = user.subscribe_user_to_strategy(strategy_id=strategy.strategy_id)
    user.record_command(command_name=f'ON {strategy.strategy_name}')
    query.answer()

    if subscribed:
        query.edit_message_text(
            text=strategy.description(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        sleep(4)

        signals_df = read_csv(
            filepath_or_buffer=f'csv/historic_signals_{strategy.strategy_id}.csv',
            sep=';',
            index_col=0,
            parse_dates=['datetime'],
            low_memory=False
        )
        signals = get_last_signals(df=signals_df, amount=3)

        for signal in signals:
            query.message.reply_html(
                text=f"{signal}", reply_markup=make_keyboard_for_signal(user.user_id, signal))

    else:
        query.edit_message_text(text=static_text.already_subscribed)
