from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.handlers.strategies.manage_data import SMA_CONNECT_BUTTON, RSI_CONNECT_BUTTON, SMA_DISCONNECT_BUTTON, \
    RSI_DISCONNECT_BUTTON
from tgbot.handlers.strategies.static_text import sma_button_text, rsi_button_text
from tgbot.handlers.strategies.utils import Signal


def make_keyboard_for_strategies_connect() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(sma_button_text,
                              callback_data=f'{SMA_CONNECT_BUTTON}')],
        [InlineKeyboardButton(rsi_button_text,
                              callback_data=f'{RSI_CONNECT_BUTTON}')]
    ]

    return InlineKeyboardMarkup(buttons)


def make_keyboard_for_strategies_disconnect() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(sma_button_text,
                              callback_data=f'{SMA_DISCONNECT_BUTTON}')],
        [InlineKeyboardButton(rsi_button_text,
                              callback_data=f'{RSI_DISCONNECT_BUTTON}')]
    ]

    return InlineKeyboardMarkup(buttons)


def make_keyboard_for_signal(user_id, signal):
    action = 'Купить' if signal.buy_flag == 1 else 'Продать'
    buttons = [[InlineKeyboardButton(action, url=signal.get_url(user_id))]]

    return InlineKeyboardMarkup(buttons)
