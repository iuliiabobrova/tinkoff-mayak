"""Здесь находятся настройки стратегий"""

std_period = 20  # дней (обязательно меньше sma_short_period)


class RsiSetting:
    period_of_daily_ema = 13  # (дней) значение для расчета экспоненциальной скользящей средней

    settings_fix = True  # включает триггер стратегии на все значения %RSI выше upper_rsi_fix и ниже lower_rsi_fix
    upper_rsi_fix = 75
    lower_rsi_fix = 25

    settings_percentile = False  # не может быть True вместе с settings_fix
    upper_rsi_percentile = 95  # 5% самых высоких значений RSI ведут к сигналу
    lower_rsi_percentile = 2.5  # 2,5% самых низких значений RSI ведут к сигналу
