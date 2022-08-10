if __name__ == '__main__':
    from tgbot.models import HistoricCandle, Share, MovingAverage

    for figi in Share.get_figi_list()[:2]:
        a = MovingAverage.get_figi_ma(figi=figi, period=49)
        print(a)
