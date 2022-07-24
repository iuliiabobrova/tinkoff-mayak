"""
    Telegram event handlers
"""
import sys
import logging
import threading
from typing import Dict

import telegram.error
from telegram import Bot, Update, BotCommand
from telegram.ext import (
    Updater, Dispatcher, Filters,
    CommandHandler, MessageHandler,
    CallbackQueryHandler,
    ConversationHandler
)

from dtb.celery import app  # event processing in async mode
from dtb.settings import TELEGRAM_TOKEN, DEBUG

from tgbot.handlers.admin import handlers as admin_handlers
from tgbot.handlers.broadcast_message import handlers as broadcast_handlers
from tgbot.handlers.broadcast_message.manage_data import CONFIRM_DECLINE_BROADCAST
from tgbot.handlers.broadcast_message.static_text import broadcast_command
from tgbot.handlers.choose_strategy import handlers as choose_strategy_handlers
from tgbot.handlers.feedback import handlers as feedback_handlers
from tgbot.handlers.feedback.manage_data import (
    ASK_FOR_FEEDBACK_STATE,
    GET_FEEDBACK_STATE,
    POSITIVE_ANSWER_BUTTON,
    NEGATIVE_ANSWER_BUTTON,
    ASK_FOR_DETAILED_FEEDBACK_BUTTON
)
from tgbot.handlers.location import handlers as location_handlers
from tgbot.handlers.onboarding import handlers as onboarding_handlers
from tgbot.handlers.stock import handlers as stock_handlers
from tgbot.handlers.strategies import handlers as strategies_handlers
from tgbot.handlers.turn_off_signals.manage_data import RSI_DISCONNECT_BUTTON, ALL_DISCONNECT_BUTTON
from tgbot.handlers.strategy_info import handlers as strategy_info_handlers
from tgbot.handlers.time import handlers as time_handlers
from tgbot.handlers.turn_off_signals import handlers as turn_off_signals_handlers
from tgbot.handlers.utils import files, error
from tgbot.models import Strategy


def setup_dispatcher(dp):
    """
    Adding handlers for events from Telegram
    """
    # onboarding
    dp.add_handler(CommandHandler("start", onboarding_handlers.command_start))

    # admin commands
    dp.add_handler(CommandHandler("admin", admin_handlers.admin))
    dp.add_handler(CommandHandler("stats", admin_handlers.stats))
    dp.add_handler(CommandHandler('export_users', admin_handlers.export_users))

    # # location TODO после удаления связей в БД удалить закомментированный код (4 строки ниже)
    # dp.add_handler(CommandHandler(
    #     "ask_location", location_handlers.ask_for_location))
    # dp.add_handler(MessageHandler(Filters.location,
    #                location_handlers.location_handler))

    # broadcast message
    dp.add_handler(
        MessageHandler(Filters.regex(
            rf'^{broadcast_command}(/s)?.*'), broadcast_handlers.broadcast_command_with_message)
    )
    dp.add_handler(
        CallbackQueryHandler(broadcast_handlers.broadcast_decision_handler,
                             pattern=f"^{CONFIRM_DECLINE_BROADCAST}")
    )

    # feedback command
    dp.add_handler(
        ConversationHandler(entry_points=[CommandHandler("feedback", feedback_handlers.command_feedback)],
                            states={
                                ASK_FOR_FEEDBACK_STATE: [
                                    CallbackQueryHandler(
                                        feedback_handlers.positive_feedback, pattern=f"^{POSITIVE_ANSWER_BUTTON}$"),
                                    CallbackQueryHandler(
                                        feedback_handlers.negative_feedback, pattern=f"^{NEGATIVE_ANSWER_BUTTON}$"),
                                    CallbackQueryHandler(feedback_handlers.ask_for_feedback,
                                                         pattern=f"^{ASK_FOR_DETAILED_FEEDBACK_BUTTON}$")],
                                GET_FEEDBACK_STATE: [
                                    MessageHandler(Filters.text & ~Filters.command, feedback_handlers.get_feedback)]},
                            fallbacks=[CommandHandler('cancel', feedback_handlers.cancel_feedback)])
    )

    # strategy command
    dp.add_handler(CommandHandler(
        "strategy", choose_strategy_handlers.command_strategy))

    # str_info command
    dp.add_handler(CommandHandler(
        "str_info", strategy_info_handlers.command_str_info))

    # handle strategy choice
    strategy_ids = list(map(lambda s: s.strategy_id, Strategy.all()))
    for identifier in strategy_ids:
        dp.add_handler(CallbackQueryHandler(
            strategies_handlers.strategy_connect, pattern=f"{identifier}_connect"))

    # handle strategy disconnect
    for identifier in strategy_ids:
        dp.add_handler(CallbackQueryHandler(
            turn_off_signals_handlers.strategy_disconnect, pattern=f"{identifier}_disconnect"))
    dp.add_handler(CallbackQueryHandler(
        turn_off_signals_handlers.all_disconnect, pattern=f"^{ALL_DISCONNECT_BUTTON}$"))

    # stock command
    dp.add_handler(CommandHandler(
        "stock", stock_handlers.command_stock))

    # time command
    dp.add_handler(CommandHandler(
        "time", time_handlers.command_time))

    # off command
    dp.add_handler(CommandHandler(
        "off", turn_off_signals_handlers.command_off))

    # files
    dp.add_handler(MessageHandler(
        Filters.animation, files.show_file_id,
    ))

    # handling errors
    dp.add_error_handler(error.send_stacktrace_to_tg_chat)

    # EXAMPLES FOR HANDLERS
    # dp.add_handler(MessageHandler(Filters.text, <function_handler>))
    # dp.add_handler(MessageHandler(
    #     Filters.document, <function_handler>,
    # ))
    # dp.add_handler(CallbackQueryHandler(<function_handler>, pattern="^r\d+_\d+"))
    # dp.add_handler(MessageHandler(
    #     Filters.chat(chat_id=int(TELEGRAM_FILESTORAGE_ID)),
    #     # & Filters.forwarded & (Filters.photo | Filters.video | Filters.animation),
    #     <function_handler>,
    # ))

    return dp


def run_pooling():
    """ Run bot in pooling mode """
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    dp = updater.dispatcher
    dp = setup_dispatcher(dp)
    j = updater.job_queue

    bot_info = Bot(TELEGRAM_TOKEN).get_me()
    bot_link = f"https://t.me/" + bot_info["username"]

    print(f"✅Pooling of '{bot_link}' started")

    updater.start_polling()
    updater.idle()


# Global variable - best way I found to init Telegram bot
bot = Bot(TELEGRAM_TOKEN)
try:
    TELEGRAM_BOT_USERNAME = bot.get_me()["username"]
except telegram.error.Unauthorized:
    logging.error(f"Invalid TELEGRAM_TOKEN.")
    sys.exit(1)


@app.task(ignore_result=True)
def process_telegram_event(update_json):
    update = Update.de_json(update_json, bot)
    dispatcher.process_update(update)


def set_up_commands(bot_instance: Bot) -> None:
    langs_with_commands: Dict[str, Dict[str, str]] = {
        'ru': {
            'strategy': 'Выбрать стратегии',
            'str_info': 'Узнать о стратегиях больше️',
            # 'stock': 'Изменить набор бумаг️',
            # 'time': 'Настроить удобное время уведомлений',
            'off': 'Отписаться от стратегий',
            'feedback': 'Оставить фидбэк'
        },
        'en': {
            'strategy': 'Выбрать стратегии',
            'str_info': 'Узнать о стратегиях больше️',
            # 'stock': 'Изменить набор бумаг️',
            # 'time': 'Настроить удобное время уведомлений',
            'off': 'Отписаться от стратегий',
            'feedback': 'Оставить фидбэк'
        }
    }

    bot_instance.delete_my_commands()

    for language_code in langs_with_commands:
        bot_instance.set_my_commands(
            language_code=language_code,
            commands=[
                BotCommand(command, description) for command, description in langs_with_commands[language_code].items()
            ]
        )


# WARNING: it's better to comment the line below in DEBUG mode.
# Likely, you'll get a flood limit control error, when restarting bot too often
set_up_commands(bot)

n_workers = 0 if DEBUG else 4
dispatcher = setup_dispatcher(Dispatcher(
    bot, update_queue=None, workers=n_workers, use_context=True))
