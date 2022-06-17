from telegram import Update
from telegram.ext import CallbackContext


def sma(update: Update, context: CallbackContext) -> None:
    print('SMA is chosen')


def rsi(update: Update, context: CallbackContext) -> None:
    print('RSI is chosen')
