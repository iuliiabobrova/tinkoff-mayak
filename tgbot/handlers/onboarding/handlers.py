from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.onboarding import static_text
from tgbot.models import User
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies


def command_start(update: Update, context: CallbackContext) -> None:
    User.get_user(update, context)

    update.message.reply_html(static_text.greetings,
                              reply_markup=make_keyboard_for_strategies(),
                              disable_web_page_preview=True)
