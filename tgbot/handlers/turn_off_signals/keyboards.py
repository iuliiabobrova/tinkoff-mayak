from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.handlers.strategies.static_text import all_button_text
from tgbot.handlers.turn_off_signals.manage_data import ALL_DISCONNECT_BUTTON
from tgbot.models import Strategy


def make_keyboard_for_strategies_disconnect(strategies: List[Strategy]) -> InlineKeyboardMarkup:
    buttons = list(map(lambda s: [InlineKeyboardButton(s.strategy_name, callback_data=f'{s.strategy_id}')], strategies))
    buttons.append([InlineKeyboardButton(all_button_text, callback_data=f'{ALL_DISCONNECT_BUTTON}')])

    return InlineKeyboardMarkup(buttons)