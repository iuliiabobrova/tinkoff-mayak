import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

sma_button_text = "Скользящее среднее (SMA)"
rsi_button_text = "RSI"
all_button_text = "Отписаться от обеих стратегий"
rsi_is_chosen = df_texts.menu[0]
sma_is_chosen = df_texts.menu[1]
sell_signal = df_texts.signal[0]
buy_signal = df_texts.signal[1]
rsi_low = df_texts.signal[2]
rsi_high = df_texts.signal[3]
sma_low = df_texts.signal[4]
sma_high = df_texts.signal[5]
already_subscribed = "Вы уже подписаны на данную стратегию"
