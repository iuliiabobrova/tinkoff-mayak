from os import environ
from django import setup
from threading import Thread
from time import sleep

environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtb.settings')
setup()  # django

from tgbot.dispatcher import run_pooling
from corestrategy import historic_data_download

if __name__ == "__main__":

    # TODO заменить Threading на потоки из Celery
    thr1 = Thread(target=historic_data_download.run_download_data).start()
    sleep(30)  # TODO refactor (sleep был, чтобы успевали подгружаться глобальные переменные data_downloading_flag, figi_list, df_shares)
    from corestrategy.historic_data_download import figi_list, df_shares
    from corestrategy import run_strat
    thr2 = Thread(target=run_strat.run_strategies, args=(figi_list, df_shares,)).start()
    from tgbot.handlers.strategies import deliery_boy
    th3 = Thread(target=deliery_boy.run_delivery_boy).start()
    run_pooling()
