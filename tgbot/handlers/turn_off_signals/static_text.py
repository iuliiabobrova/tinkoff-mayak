import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

off_signals = df_texts.off_signals[0]
