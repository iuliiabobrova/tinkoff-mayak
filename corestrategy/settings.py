# в этом файле находятся настройки стратегий
"""SMA"""
from typing import List
from django.db.models import QuerySet

std_period = 20  # дней (обязательно меньше sma_short_period)


class SMACrossPeriods:
    def __init__(self, short, long):
        self.short = short
        self.long = long


sma_cross_periods_50_200 = SMACrossPeriods(50, 200)
sma_cross_periods_30_90 = SMACrossPeriods(30, 90)
sma_cross_periods_20_60 = SMACrossPeriods(20, 60)

sma_cross_periods_all = [
    sma_cross_periods_50_200,
    sma_cross_periods_30_90,
    sma_cross_periods_20_60
]

"""RSI"""
period_of_ema = 13  # (дней) значение для расчета экспоненциальной скользящей средней

settings_fix = True  # включает триггер стратегии на все значения %RSI выше upper_rsi_fix и ниже lower_rsi_fix
upper_rsi_fix = 75
lower_rsi_fix = 25

settings_percentile = False  # не может быть True вместе с settings_fix
upper_rsi_percentile = 95  # 5% самых высоких значений RSI ведут к сигналу
lower_rsi_percentile = 2.5  # 2,5% самых низких значений RSI ведут к сигналу

columns_rsi = ['figi',
               'ticker',
               'share_name',
               'datetime',
               'last_price',
               'rsi_float',
               'buy_flag',
               'strategy_id',
               'profit',
               'currency',
               'country']
columns_sma = ['figi',
               'ticker',
               'share_name',
               'datetime',
               'last_price',
               'buy_flag',
               'strategy_id',
               'profit',
               'currency',
               'country']
