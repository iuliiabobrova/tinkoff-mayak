from telegram import Update
from telegram.ext import CallbackContext

from tgbot import static_text
from tgbot.models import User
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_connect
from tgbot.models import Strategy


def command_start(update: Update, context: CallbackContext) -> None:
    user = User.get_user(update, context)
    user.record_command(command_name="start")

    subscriptions = list(map(lambda item: item.strategy_id, user.user_subscriptions()))
    available_strategies = list(filter(lambda s: s.strategy_id not in subscriptions, Strategy.all()))

    user_ids = list(map(lambda item: item.user_id, User.objects.all()))
    if user.user_id not in user_ids:
        disclaimer_message = update.message.reply_html(
            static_text.disclaimer,
            disable_web_page_preview=True
        )
        disclaimer_message.pin()

    update.message.reply_html(
        static_text.greetings,
        reply_markup=make_keyboard_for_strategies_connect(available_strategies),
        disable_web_page_preview=True
    )
