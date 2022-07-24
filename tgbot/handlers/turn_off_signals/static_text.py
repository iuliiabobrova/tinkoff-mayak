import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

off_signals = df_texts.off_signals[0]
what_to_disconnect = df_texts.off_signals[1]

no_subscriptions_to_strategy = df_texts.off_signals[3]
no_signals = "Сейчас сигналы выключены.\n" \
             "Чтобы подключить их введите команду /strategy"


def strategy_off_signals(name: str) -> str:
    df_texts.off_signals[2] % name
