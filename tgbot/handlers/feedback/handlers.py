from telegram import Update
from telegram.ext import CallbackContext

from tgbot.handlers.feedback import static_text
from tgbot.models import User, FeedbackMessage
from tgbot.handlers.feedback.manage_data import ASK_FOR_FEEDBACK_STATE, GET_FEEDBACK_STATE, END_FEEDBACK_STATE
from tgbot.handlers.feedback.keyboards import make_keyboard_for_feedback_command


def command_feedback(update: Update, context: CallbackContext) -> int:
    User.get_user(update, context)

    update.message.reply_text(
        text=static_text.ask_feedback, reply_markup=make_keyboard_for_feedback_command())

    return ASK_FOR_FEEDBACK_STATE


def positive_feedback(update: Update, context: CallbackContext) -> int:
    u = User.get_user(update, context)
    u.record_command_event("positive_feedback")

    FeedbackMessage.create(
        update, context, message=static_text.positive_answer_button_text)
    query = update.callback_query
    query.answer()

    query.edit_message_text(static_text.positive_answer)

    return END_FEEDBACK_STATE


def negative_feedback(update: Update, context: CallbackContext) -> int:
    u = User.get_user(update, context)
    u.record_command_event("negative_feedback")

    query = update.callback_query
    query.answer()

    query.edit_message_text(static_text.negative_answer)

    return GET_FEEDBACK_STATE


def ask_for_feedback(update: Update, _: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    query.edit_message_text(static_text.feedback_text)

    return GET_FEEDBACK_STATE


def get_feedback(update: Update, context: CallbackContext) -> int:
    FeedbackMessage.create(update, context)

    update.message.reply_text(
        static_text.thanks_for_feedback.format(message=update.message.text))

    return END_FEEDBACK_STATE


def cancel_feedback(update: Update, context: CallbackContext) -> int:
    u = User.get_user(update, context)
    u.record_command_event("cancel_feedback")

    update.message.reply_text(static_text.feedback_cancelled)

    return END_FEEDBACK_STATE
