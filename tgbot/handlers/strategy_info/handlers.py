from telegram import Update
from telegram.ext import CallbackContext

from tgbot import static_text
from tgbot.models import User, Command


def command_str_info(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="str_info",
                   user_id=u.user_id, username=u.username)
    update.message.reply_html(
        static_text.strategy_with_links, disable_web_page_preview=True)
