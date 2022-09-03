import asyncio
from os import environ
from django import setup


environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtb.settings')
setup()  # django

from tgbot.dispatcher import run_polling
from corestrategy.run_strat import run_strategies


if __name__ == "__main__":
    asyncio.run(run_strategies())
