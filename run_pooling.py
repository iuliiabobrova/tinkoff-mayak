from os import environ
from django import setup
from threading import Thread
from time import sleep

from corestrategy import historic_data_download, run_strat

environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtb.settings')
setup()  # django

from tgbot.dispatcher import run_pooling
from tgbot.handlers.strategies.deliery_boy import run_delivery_boy

if __name__ == "__main__":

    # TODO заменить Threading на потоки из Celery
    thr1 = Thread(target=historic_data_download.run_download_data).start()
    sleep(3)  # TODO refactor (sleep был, чтобы успевали подгружаться глобальные переменные figi_list, df_shares)
    from corestrategy.historic_data_download import figi_list, df_shares
    thr2 = Thread(target=run_strat.run_strategies, args=(figi_list, df_shares,)).start()
    run_pooling()
    th3 = Thread(target=run_delivery_boy).start()
