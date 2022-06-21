import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

sma_strategy_link = df_texts.str_info[0]
rsi_strategy_link = df_texts.str_info[1]
strategy_info = df_texts.strategy_choice[3]
strategy_with_links = (f'{strategy_info}\n'
                       f'\n'
                       f'<a href="{sma_strategy_link}"><b>Перепроданность по RSI</b></a>\n'
                       f'<a href="{rsi_strategy_link}"><b>Среднее скользящее (cross-SMA)</b></a>')
