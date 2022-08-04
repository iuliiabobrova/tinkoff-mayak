from pandas import read_csv
from tgbot.handlers.strategies.utils import Signal
import decimal
from corestrategy.utils import func_duration


@func_duration
def dura():
    for i in range(9999):
        print(2)


a = dura()
print(a)
