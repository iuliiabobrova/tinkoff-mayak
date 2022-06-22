from pandas import DataFrame, read_csv
from time import sleep
from dtb.settings import TELEGRAM_TOKEN as tg_token
from os.path import exists

from tgbot.models import User
from tgbot.handlers.strategies.utils import get_last_signal
from tgbot.handlers.strategies.keyboards import make_keyboard_for_signal
from tgbot.handlers.broadcast_message.utils import _send_message

from corestrategy.strategy_sma import columns_sma
from corestrategy.strategy_rsi import columns_rsi


def send_signal_to_strategy_subscribers(df: DataFrame) -> None:
    signal = get_last_signal(df=df)
    strategy_id = signal.strategy_id
    users_with_strategy = User.get_users_with_strategy_subscription(strategy_id=strategy_id)
    for user in users_with_strategy:
        _send_message(text=f"{signal}",
                      user_id=user.user_id,
                      tg_token=tg_token,
                      disable_web_page_preview=True,
                      reply_markup=make_keyboard_for_signal(user.user_id, signal))
        sleep(0.4)

    print("Signal sent!")


# TODO можно рассылать сообщение через эту штуку через
# telegram api https://github.com/python-telegram-bot/python-telegram-bot/wiki/Extensions-–-JobQueue
# чтобы не делать бесконечный цикл и sleep
def run_delivery_boy():

    global data_downloading_flag

    previous_size_df_sma = 9999999
    previous_size_df_rsi = 9999999

    while True:
        from corestrategy.historic_data_download import data_downloading_flag
        if data_downloading_flag == False:
            if exists('csv/actual_signals_rsi.csv'):
                df_rsi = read_csv(filepath_or_buffer='csv/actual_signals_rsi.csv',
                                                 sep=';',
                                                 index_col=0)
            else:
                sleep(60)
                run_delivery_boy()
            if exists('csv/actual_signals_sma.csv'):
                df_sma = read_csv(filepath_or_buffer='csv/actual_signals_sma.csv',
                                                 sep=';',
                                                 index_col=0)
            else:
                sleep(60)
                run_delivery_boy()

            size_df_sma = df_sma.size
            size_df_rsi = df_rsi.size

            if size_df_sma > previous_size_df_sma:
                send_signal_to_strategy_subscribers(df=df_sma)

            if size_df_rsi > previous_size_df_rsi:
                send_signal_to_strategy_subscribers(df=df_rsi)

            previous_size_df_sma = size_df_sma
            previous_size_df_rsi = size_df_rsi

            sleep(60)
        else:
            sleep(60)
