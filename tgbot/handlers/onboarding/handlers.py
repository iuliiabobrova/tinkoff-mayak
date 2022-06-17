from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.onboarding import static_text
from tgbot.models import User
from tgbot.handlers.onboarding.keyboards import make_keyboard_for_start_command


def command_start(update: Update, context: CallbackContext) -> None:
    User.get_user(update, context)

    update.message.reply_html(static_text.greetings,
                              reply_markup=make_keyboard_for_start_command(),
                              disable_web_page_preview=True)


def sma(update: Update, context: CallbackContext) -> None:
    pass


def rsi(update: Update, context: CallbackContext) -> None:
    pass
