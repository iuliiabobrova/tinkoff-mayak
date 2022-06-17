from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.handlers.onboarding.manage_data import SMA_BUTTON, RSI_BUTTON
from tgbot.handlers.onboarding.static_text import sma_button_text, rsi_button_text


def make_keyboard_for_start_command() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(sma_button_text,
                              callback_data=f'{SMA_BUTTON}')],
        [InlineKeyboardButton(rsi_button_text,
                              callback_data=f'{RSI_BUTTON}')]
    ]

    return InlineKeyboardMarkup(buttons)
