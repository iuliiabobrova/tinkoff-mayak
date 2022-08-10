from telegram import Update
from telegram.ext import CallbackContext

from tgbot import static_text
from tgbot.models import User, Command


def command_str_info(update: Update, context: CallbackContext) -> None:
    user = User.get_user(update, context)
    user.record_command(command_name="str_info")

    update.message.reply_html(
        static_text.strategy_with_links, disable_web_page_preview=True)
