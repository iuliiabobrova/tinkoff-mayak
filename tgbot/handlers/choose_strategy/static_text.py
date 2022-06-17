import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

add_new_strategy = df_texts.strategy[0]
