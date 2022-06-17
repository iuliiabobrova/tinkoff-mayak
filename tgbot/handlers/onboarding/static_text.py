
import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

hello = df_texts.hello[1]
hello_2 = df_texts.hello[2]

sma_strategy_link = df_texts.str_info[0]
rsi_strategy_link = df_texts.str_info[1]

greetings = (f'{hello}\n'
             f'\n'
             f'<a href="{sma_strategy_link}"><b>Среднее скользящее (cross-SMA)</b></a>\n'
             f'<a href="{rsi_strategy_link}"><b>Перепроданность по RSI</b></a>\n'
             f'\n'
             f'{hello_2}')
