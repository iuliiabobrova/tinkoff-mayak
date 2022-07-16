from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.handlers.strategies.static_text import sma_button_text, rsi_button_text, all_button_text
from tgbot.handlers.turn_off_signals.manage_data import SMA_DISCONNECT_BUTTON, RSI_DISCONNECT_BUTTON, \
    ALL_DISCONNECT_BUTTON


def make_keyboard_for_strategies_disconnect(strategies: List[str]) -> InlineKeyboardMarkup:
    buttons = []
    for strategy in strategies:
        if strategy == 'sma':
            buttons.append([InlineKeyboardButton(sma_button_text, callback_data=f'{SMA_DISCONNECT_BUTTON}')])
        elif strategy == 'rsi':
            buttons.append([InlineKeyboardButton(rsi_button_text, callback_data=f'{RSI_DISCONNECT_BUTTON}')])
    buttons.append([InlineKeyboardButton(all_button_text, callback_data=f'{ALL_DISCONNECT_BUTTON}')])

    return InlineKeyboardMarkup(buttons)