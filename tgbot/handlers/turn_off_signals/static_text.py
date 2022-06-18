import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

off_signals = df_texts.off_signals[0]
no_signals = "Сейчас сигналы выключены.\n" \
    "Чтобы подключить их введите команду /strategy"
