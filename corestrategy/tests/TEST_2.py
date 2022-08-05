import asyncio
import time

from pandas import read_csv
from tgbot.handlers.strategies.utils import Signal
import decimal

from corestrategy.utils import Limit


@Limit(calls=5, period=2)
async def test_call(x):
    print(x)


async def worker():
    for x in range(100):
        await test_call(x + 1)


asyncio.run(worker())
