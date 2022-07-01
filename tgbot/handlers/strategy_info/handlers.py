from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.strategy_info import static_text
from tgbot.models import User


def command_str_info(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    u.record_command_event("str_info")
    update.message.reply_html(
        static_text.strategy_with_links, disable_web_page_preview=True)
