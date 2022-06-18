import os

from pandas import DataFrame, read_csv
from time import sleep
from dtb.settings import TELEGRAM_TOKEN as tg_token

from tgbot.models import User
from tgbot.handlers.strategies.utils import get_last_signal
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.handlers.broadcast_message.utils import _send_message


def send_signal_to_strategy_subscribers(df: DataFrame) -> None:
    signal = get_last_signal(df=df)
    strategy_id = signal['strategy_id']
    user_ids = []

    for user_id in user_ids:
        try:
            _send_message(text=f"{signal}",
                          user_id=user_id,
                          tg_token=tg_token,
                          disable_web_page_preview=True,
                          reply_markup=make_keyboard_for_signal(user_id, signal))

        except Exception as e:
            print(f"Failed to send message to {user_id}, reason: {e}")
        sleep(0.4)

    print("Signal sent!")


# можно рассылать сообщение через эту штуку через telegram api https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions-–-JobQueue
# чтобы не делать бесконечный цикл и sleep
def run_delivery_boy():
    previous_size_df_sma = 9999999
    previous_size_df_rsi = 9999999

    if not os.path.exists('csv/actual_signals_sma.csv'):
        df_signals_sma = DataFrame(columns=['figi',
                                            'ticker',
                                            'share_name',
                                            'datetime',
                                            'last_price',
                                            'sell_flag',
                                            'buy_flag',
                                            'strategy_id',
                                            'profit',
                                            'currency'],
                                   index="figi")
        df_signals_sma.to_csv('csv/actual_signals_sma.csv', sep=';')

    if not os.path.exists('csv/actual_signals_rsi.csv'):
        df_signals_rsi = DataFrame(columns=['figi',
                                            'ticker',
                                            'share_name',
                                            'datetime',
                                            'last_price',
                                            'rsi_float',
                                            'sell_flag',
                                            'buy_flag',
                                            'strategy_id',
                                            'profit',
                                            'currency'],
                                   index="figi")
        df_signals_rsi.to_csv('csv/actual_signals_rsi.csv', sep=';')

    while True:
        df_sma = read_csv('csv/actual_signals_sma.csv', sep=';')
        df_rsi = read_csv('csv/actual_signals_rsi.csv', sep=';')
        size_df_sma = df_sma.size
        size_df_rsi = df_rsi.size

        if size_df_sma > previous_size_df_sma:
            send_signal_to_strategy_subscribers(df=df_sma)

        if size_df_rsi > previous_size_df_rsi:
            send_signal_to_strategy_subscribers(df=df_rsi)

        previous_size_df_sma = size_df_sma
        previous_size_df_rsi = size_df_rsi

        sleep(60)
