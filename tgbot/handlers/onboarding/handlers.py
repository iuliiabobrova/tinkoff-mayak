from telegram import Update
from telegram.ext import CallbackContext

from tgbot import static_text
from tgbot.models import User, Command, Strategy
from tgbot.handlers.strategies.keyboards import make_keyboard_for_strategies_connect


def command_start(update: Update, context: CallbackContext) -> None:
    u = User.get_user(update, context)
    Command.record(command_name="start", user_id=u.user_id, username=u.username)

    subscriptions = list(map(lambda item: item.strategy_id, u.user_subscriptions()))
    available_strategies = list(filter(lambda s: s.strategy_id not in subscriptions, Strategy.all()))

    user_ids = list(map(lambda item: item.user_id, User.objects.all()))
    if u.user_id not in user_ids:
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
