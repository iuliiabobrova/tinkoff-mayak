from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.onboarding import static_text
from tgbot.models import User, Command
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_connect


def command_start(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="start",
                   user_id=u.user_id, username=u.username)

    disclaimer_message = update.message.reply_html(static_text.disclaimer,
                                                   disable_web_page_preview=True)
    disclaimer_message.pin()

    update.message.reply_html(static_text.greetings,
                              reply_markup=make_keyboard_for_strategies_connect(),
                              disable_web_page_preview=True)
