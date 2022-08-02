

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.handlers.feedback.manage_data import (
    POSITIVE_ANSWER_BUTTON, NEGATIVE_ANSWER_BUTTON, ASK_FOR_DETAILED_FEEDBACK_BUTTON
)
from tgbot.static_text import (
    positive_answer_button_text, negative_answer_button_text, ask_for_detailed_feedback_button_text
)

def make_keyboard_for_feedback_command() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(positive_answer_button_text, callback_data=f'{POSITIVE_ANSWER_BUTTON}'),
         InlineKeyboardButton(negative_answer_button_text, callback_data=f'{NEGATIVE_ANSWER_BUTTON}')],
        [InlineKeyboardButton(ask_for_detailed_feedback_button_text,
                              callback_data=f'{ASK_FOR_DETAILED_FEEDBACK_BUTTON}')]
    ]

    return InlineKeyboardMarkup(buttons)
