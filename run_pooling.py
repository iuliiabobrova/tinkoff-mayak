from os import environ
from django import setup
from threading import Thread

environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtb.settings')
setup()  # django

from tgbot.dispatcher import run_pooling
from corestrategy.run_strat import run_strategies

if __name__ == "__main__":
    # TODO заменить Thread на Task
    # thr1 = Thread(target=run_strategies).start() # Disable for ABC test
    run_pooling()
