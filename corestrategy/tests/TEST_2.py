from pandas import read_csv
from tgbot.handlers.strategies.utils import Signal

df = read_csv(filepath_or_buffer='../../csv/historic_signals_sma_20_60.csv', sep=';')
signals = df.tail(4).to_dict('records')
print(signals)
a = list(map(lambda x: Signal(**x), signals))
print(a[0])
