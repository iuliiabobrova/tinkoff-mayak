from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from tgbot.models import Strategy


def make_keyboard_for_strategies_connect() -> InlineKeyboardMarkup:
    buttons = map(lambda s: [InlineKeyboardButton(s.strategy_name, callback_data=f'{s.strategy_id}')], Strategy.all())
    return InlineKeyboardMarkup(list(buttons))


def make_keyboard_for_signal(user_id, signal):
    action = 'Купить' if signal.buy_flag == 1 else 'Продать'
    buttons = [[InlineKeyboardButton(action, url=signal.get_url(user_id))]]

    return InlineKeyboardMarkup(buttons)
