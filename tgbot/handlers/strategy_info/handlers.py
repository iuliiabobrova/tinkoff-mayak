from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.strategy_info import static_text


def command_str_info(update: Update, context: CallbackContext) -> None:
    update.message.reply_html(
        static_text.strategy_with_links, disable_web_page_preview=True)
