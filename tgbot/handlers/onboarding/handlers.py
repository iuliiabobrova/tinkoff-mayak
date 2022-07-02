from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.onboarding import static_text
from tgbot.models import User, Command
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies


def command_start(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="start",
                   user_id=u.user_id, username=u.username)

    update.message.reply_html(static_text.greetings,
                              reply_markup=make_keyboard_for_strategies(),
                              disable_web_page_preview=True)
