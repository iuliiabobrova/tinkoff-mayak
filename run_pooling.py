from os import environ
from django import setup
from threading import Thread
from time import sleep

environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtb.settings')
setup()  # django

from tgbot.dispatcher import run_pooling
from corestrategy.historic_data_download import run_download_data
from corestrategy.run_strat import run_strategies

if __name__ == "__main__":
    # TODO заменить Thread на Task
    figi_list, df_shares = run_download_data()
    thr1 = Thread(target=run_strategies, args=(figi_list, df_shares,)).start()
    run_pooling()
