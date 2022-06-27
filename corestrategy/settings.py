# в этом файле находятся настройки стратегий
"""SMA"""
std_period = 20  # дней (обязательно меньше sma_short_period)
period_of_short_sma = 50  # (дней) (обязательно меньше sma_long_period) короткая скользящая средняя
period_of_long_sma = 200  # (дней) длинная скользящая средняя

"""RSI"""
period_of_ema = 13  # (дней) значение для расчета экспоненциальной скользящей средней

settings_fix = True  # включает триггер стратегии на все значения %RSI выше upper_rsi_fix и ниже lower_rsi_fix
upper_rsi_fix = 70
lower_rsi_fix = 30

settings_percentile = False  # не может быть True вместе с settings_fix
upper_rsi_percentile = 95  # 5% самых высоких значений RSI ведут к сигналу
lower_rsi_percentile = 2.5  # 2,5% самых низких значений RSI ведут к сигналу

columns_rsi = ['figi',
               'ticker',
               'share_name',
               'datetime',
               'last_price',
               'rsi_float',
               'sell_flag',
               'buy_flag',
               'strategy_id',
               'profit',
               'currency']
columns_sma = ['figi',
               'ticker',
               'share_name',
               'datetime',
               'last_price',
               'sell_flag',
               'buy_flag',
               'strategy_id',
               'profit',
               'currency']
