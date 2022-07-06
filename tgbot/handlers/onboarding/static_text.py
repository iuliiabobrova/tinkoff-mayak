
import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

hello = df_texts.hello[1]
hello_2 = df_texts.hello[2]

sma_strategy_link = df_texts.str_info[0]
rsi_strategy_link = df_texts.str_info[1]

disclaimer_link = "https://telegra.ph/Tinkoff-Mayak-07-05"

disclaimer = (f'Не является индивидуальной инвестиционной <a href="{disclaimer_link}"><b>рекомендацией</b></a>.\n'
              f'Предоставляемая информация содержит результаты исследований в отношении финансовых инструментов, распространяемая путем рассылки посредством телеграмм бота.')
greetings = f'{hello}'
