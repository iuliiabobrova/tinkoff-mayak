from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Union, Optional, Tuple, List

import tinkoff.invest.schemas as schemas
from django.db import models
from django.db.models import QuerySet, Manager
from numpy import number
from telegram import Update
from telegram.ext import CallbackContext
from tinkoff.invest import Share
from tinkoff.invest.utils import quotation_to_decimal

from dtb.settings import DEBUG
from tgbot.static_text import (
    sma_50_200_is_chosen, rsi_is_chosen, sma_30_90_is_chosen, sma_20_60_is_chosen
)
from tgbot.handlers.utils.info import extract_user_data_from_update
from utils.models import CreateUpdateTracker, nb, CreateTracker, GetOrNoneManager


class AdminUserManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_admin=True)


class Strategy(CreateTracker):
    _all_cases = {
        'rsi': 'RSI',
        'sma_50_200': 'cross-SMA 50-200',
        'sma_30_90': 'cross-SMA 30-90',
        'sma_20_60': 'cross-SMA 20-60'
    }

    def __init__(self, strategy_id: str, strategy_name: Optional[str] = None):
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name or Strategy._all_cases[strategy_id]

    @classmethod
    def sma_50_200(cls) -> Strategy:
        return Strategy(strategy_id='sma_50_200')

    @classmethod
    def sma_30_90(cls) -> Strategy:
        return Strategy(strategy_id='sma_30_90')

    @classmethod
    def sma_20_60(cls) -> Strategy:
        return Strategy(strategy_id='sma_20_60')

    @classmethod
    def rsi(cls) -> Strategy:
        return Strategy(strategy_id='rsi')

    @classmethod
    def all(cls) -> List[Strategy]:
        return [cls.rsi(), cls.sma_50_200(), cls.sma_30_90(), cls.sma_20_60()]

    @classmethod
    def name(cls, strategy_id: str) -> str:
        return cls._all_cases[strategy_id]

    def description(self) -> str:
        if self.strategy_id.startswith('sma_50_200'):
            return sma_50_200_is_chosen
        elif self.strategy_id.startswith('sma_30_90'):
            return sma_30_90_is_chosen
        elif self.strategy_id.startswith('sma_20_60'):
            return sma_20_60_is_chosen
        elif self.strategy_id.startswith('rsi'):
            return rsi_is_chosen


class Subscription(CreateTracker):
    id = models.BigAutoField(primary_key=True)
    strategy_id = models.CharField(max_length=32, **nb)

    def __str__(self) -> str:
        return self.strategy_id

    @classmethod
    def create_subscription(cls, strategy_id: str) -> Subscription:
        return cls.objects.create(strategy_id=strategy_id)


class Command(CreateTracker):
    command_id = models.BigAutoField(primary_key=True)
    command_name = models.CharField(max_length=32, **nb)
    user_id = models.PositiveBigIntegerField()
    username = models.CharField(max_length=32, **nb)

    def __str__(self) -> str:
        return self.command_name

    @classmethod
    def record(cls, command_name: str, user_id: int, username: str):
        cls.objects.create(command_name=command_name,
                           user_id=user_id, username=username)

    @classmethod
    def get_command_counter(cls, command_name: str) -> number:
        return cls.objects.filter(command_name=command_name).count()

    @classmethod
    def get_command_counter_for_user(cls, command_name: str, username_or_user_id: Union[str, int]) -> number:
        username = str(username_or_user_id).replace("@", "").strip().lower()
        if username.isdigit():
            return cls.objects.filter(command_name=command_name, user_id=int(username)).count()
        return cls.objects.filter(command_name=command_name, username__iexact=username).count()

    @classmethod
    def get_commands_counter(cls):
        pass


class User(CreateUpdateTracker):
    user_id = models.PositiveBigIntegerField(primary_key=True)  # telegram_id
    username = models.CharField(max_length=32, **nb)
    first_name = models.CharField(max_length=256)
    last_name = models.CharField(max_length=256, **nb)
    language_code = models.CharField(
        max_length=8, help_text="Telegram client's lang", **nb)
    deep_link = models.CharField(max_length=64, **nb)

    is_blocked_bot = models.BooleanField(default=False)

    is_admin = models.BooleanField(default=False)

    # Под капотом создается таблица связей user_id - id подписки на стратегию
    # В будущем поможет указывать юзеру несколько стратегий
    subscriptions = models.ManyToManyField(Subscription, blank=True)

    objects = GetOrNoneManager()  # user = User.objects.get_or_none(user_id=<some_id>)
    admins = AdminUserManager()  # User.admins.all()

    def __str__(self):
        return f'@{self.username}' if self.username is not None else f'{self.user_id}'

    @classmethod
    def get_user_and_created(cls, update: Update, context: CallbackContext) -> Tuple[User, bool]:
        """ python-telegram-bot's Update, Context --> User instance """
        data = extract_user_data_from_update(update)
        u, created = cls.objects.update_or_create(
            user_id=data["user_id"], defaults=data)

        if created:
            # Save deep_link to User model
            if context is not None and context.args is not None and len(context.args) > 0:
                payload = context.args[0]
                # you can't invite yourself
                if str(payload).strip() != str(data["user_id"]).strip():
                    u.deep_link = payload
                    u.save()

        return u, created

    @classmethod
    def get_user(cls, update: Update, context: CallbackContext) -> User:
        u, _ = cls.get_user_and_created(update, context)
        return u

    @classmethod
    def get_user_by_username_or_user_id(cls, username_or_user_id: Union[str, int]) -> Optional[User]:
        """ Search user in DB, return User or None if not found """
        username = str(username_or_user_id).replace("@", "").strip().lower()
        if username.isdigit():  # user_id
            return cls.objects.filter(user_id=int(username)).first()
        return cls.objects.filter(username__iexact=username).first()

    @classmethod
    def get_users_with_strategy_subscription(cls, strategy_id: str) -> QuerySet[User]:
        return cls.objects.filter(subscriptions__strategy_id=strategy_id)

    def subscribe_user_to_strategy(self, strategy_id: str) -> bool:
        # TODO: проверка не понадобится, если разрешим несколько подписок
        has_subscription = self.subscriptions.filter(
            strategy_id=strategy_id).exists()

        if not has_subscription:
            subscription = Subscription.create_subscription(
                strategy_id=strategy_id)
            self.subscriptions.add(subscription)

        return not has_subscription

    def user_subscriptions(self) -> List[Subscription]:
        return list(self.subscriptions.all())

    def unsubscribe_user_from_all_strategies(self) -> bool:
        query = self.subscriptions.all()
        unsubscribed = query.exists()

        if unsubscribed:
            query.delete()

        return unsubscribed

    def unsubscribe_user_from_strategy(self, strategy_id: str) -> bool:
        query = self.subscriptions.filter(strategy_id=strategy_id)
        unsubscribed = query.exists()

        if unsubscribed:
            query.delete()

        return unsubscribed

    @property
    def invited_users(self) -> QuerySet[User]:
        return User.objects.filter(deep_link=str(self.user_id), created_at__gt=self.created_at)

    @property
    def tg_str(self) -> str:
        if self.username:
            return f'@{self.username}'
        return f"{self.first_name} {self.last_name}" if self.last_name else f"{self.first_name}"


class FeedbackMessage(CreateTracker):
    id = models.BigAutoField(primary_key=True)
    update_id = models.IntegerField(unique=True)
    text = models.CharField(max_length=4096)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f'{self.text}'

    @classmethod
    def create(cls, update: Update, context: CallbackContext, message=None):
        user = User.get_user(update, context)
        text = message or update.message.text

        cls.objects.create(
            user=user, update_id=update.update_id, text=text)


class Location(CreateTracker):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()

    objects = GetOrNoneManager()

    def __str__(self):
        return f"user: {self.user}, created at {self.created_at.strftime('(%H:%M, %d %B %Y)')}"

    def save(self, *args, **kwargs):
        super(Location, self).save(*args, **kwargs)
        # Parse location with arcgis
        from arcgis.tasks import save_data_from_arcgis
        if DEBUG:
            save_data_from_arcgis(latitude=self.latitude,
                                  longitude=self.longitude, location_id=self.pk)
        else:
            save_data_from_arcgis.delay(
                latitude=self.latitude, longitude=self.longitude, location_id=self.pk)


class HistoricCandle(models.Model):
    open_price = models.DecimalField()
    high_price = models.DecimalField()
    low_price = models.DecimalField()
    close_price = models.DecimalField()
    volume = models.IntegerField()
    date_time = models.DateTimeField()
    figi = models.CharField(max_length=32, **nb)

    @classmethod
    def create(cls, candle: schemas.HistoricCandle, figi: str) -> None:
        date_time = datetime(
            year=candle.time.year,
            month=candle.time.month,
            day=candle.time.day
        )
        cls.objects.create(
            open_price=quotation_to_decimal(candle.open),
            close_price=quotation_to_decimal(candle.close),
            high_price=quotation_to_decimal(candle.high),
            low_price=quotation_to_decimal(candle.low),
            volume=candle.volume,
            date_time=date_time,
            figi=figi
        )

    @classmethod
    def get_candles_by_figi(cls, figi: str) -> List[HistoricCandle]:
        return list(cls.objects.filter(figi=figi))

    @classmethod
    def get_last_datetime_by_figi(cls, figi: str) -> Optional[datetime]:
        return max(map(lambda candle: candle.date_time, cls.get_candles_by_figi(figi=figi)))


class Share(models.Model):
    figi: models.CharField(max_length=32, **nb)
    ticker: models.CharField(max_length=32, **nb)
    class_code: models.CharField(max_length=32, **nb)
    isin: models.CharField(max_length=32, **nb)
    lot: models.IntegerField(default=1)
    currency: models.CharField(max_length=32, **nb)
    klong: models.DecimalField()
    kshort: models.DecimalField()
    dlong: models.DecimalField()
    dshort: models.DecimalField()
    dlong_min: models.DecimalField()
    dshort_min: models.DecimalField()
    short_enabled_flag: models.BooleanField(default=False)
    name: models.CharField(max_length=32, **nb)
    exchange: models.CharField(max_length=32, **nb)
    ipo_date: models.DateTimeField()
    issue_size: models.IntegerField()
    country_of_risk: models.CharField(max_length=32, **nb)
    country_of_risk_name: models.CharField(max_length=32, **nb)
    sector: models.CharField(max_length=32, **nb)
    issue_size_plan: models.IntegerField()
    trading_status: models.IntegerField()
    otc_flag: models.BooleanField(default=False)
    buy_available_flag: models.BooleanField(default=False)
    sell_available_flag: models.BooleanField(default=False)
    div_yield_flag: models.BooleanField(default=False)
    share_type: models.IntegerField()
    min_price_increment: models.DecimalField()
    api_trade_available_flag: models.BooleanField(default=False)

    @classmethod
    def create(cls, share: schemas.Share):
        cls.objects.create(
            figi=share.figi,
            ticker=share.ticker,
            class_code=share.class_code,
            isin=share.isin,
            lot=share.lot,
            currency=share.currency,
            klong=quotation_to_decimal(share.klong),
            kshort=quotation_to_decimal(share.kshort),
            dlong=quotation_to_decimal(share.dlong),
            dshort=quotation_to_decimal(share.dshort),
            dlong_min=quotation_to_decimal(share.dlong_min),
            dshort_min=quotation_to_decimal(share.dshort_min),
            short_enabled_flag=share.short_enabled_flag,
            name=share.name,
            exchange=share.exchange,
            ipo_date=share.ipo_date,
            issue_size=share.issue_size,
            country_of_risk=share.country_of_risk,
            country_of_risk_name=share.country_of_risk_name,
            sector=share.sector,
            issue_size_plan=share.issue_size_plan,
            trading_status=share.trading_status,
            otc_flag=share.otc_flag,
            buy_available_flag=share.buy_available_flag,
            sell_available_flag=share.sell_available_flag,
            div_yield_flag=share.div_yield_flag,
            share_type=share.share_type,
            min_price_increment=share.min_price_increment,
            api_trade_available_flag=share.api_trade_available_flag
        )
