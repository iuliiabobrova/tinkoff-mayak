from __future__ import annotations

from datetime import datetime
from typing import Union, Optional, Tuple, List

import tinkoff.invest.schemas as schemas
from asgiref.sync import sync_to_async
from dateutil.tz import tzutc
from django.db import models
from django.db.models import QuerySet, Manager
from numpy import number
from telegram import Update
from telegram.ext import CallbackContext
from tinkoff.invest.utils import quotation_to_decimal

from corestrategy.utils import get_attributes_list
from tgbot.handlers.utils.info import extract_user_data_from_update
from tgbot.static_text import sma_50_200_is_chosen, sma_20_60_is_chosen, rsi_is_chosen, sma_30_90_is_chosen
from utils.models import CreateUpdateTracker, nb, CreateTracker, GetOrNoneManager


class AdminUserManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_admin=True)


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

    def __str__(self) -> str:
        return self.command_name

    @classmethod
    def create(cls, command_name: str) -> Command:
        return cls.objects.create(command_name=command_name)

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
    subscriptions = models.ManyToManyField(Subscription, blank=True)
    commands = models.ManyToManyField(Command, blank=True)
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

    def record_command(self, command_name: str):
        command = Command.create(command_name=command_name)
        self.commands.add(command)

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
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)

    def __str__(self) -> str:
        return f'{self.text}'

    @classmethod
    def create(cls, update: Update, context: CallbackContext, message=None):
        user = User.get_user(update, context)
        text = message or update.message.text

        cls.objects.create(
            user=user, update_id=update.update_id, text=text)


class Share(models.Model):
    uid = models.CharField(max_length=32)
    figi = models.CharField(max_length=32, null=False, primary_key=True, unique=True)
    ticker = models.CharField(max_length=32, **nb)
    class_code = models.CharField(max_length=32, **nb)
    isin = models.CharField(max_length=32, **nb)
    lot = models.IntegerField(default=1)
    currency = models.CharField(max_length=32, **nb)
    klong = models.DecimalField(max_digits=18, decimal_places=9)
    kshort = models.DecimalField(max_digits=18, decimal_places=9)
    dlong = models.DecimalField(max_digits=18, decimal_places=9)
    dshort = models.DecimalField(max_digits=18, decimal_places=9)
    dlong_min = models.DecimalField(max_digits=18, decimal_places=9)
    dshort_min = models.DecimalField(max_digits=18, decimal_places=9)
    short_enabled_flag = models.BooleanField(default=False)
    name = models.CharField(max_length=32, **nb)
    exchange = models.CharField(max_length=32, **nb)
    ipo_date = models.DateTimeField()
    issue_size = models.IntegerField()
    country_of_risk = models.CharField(max_length=32, **nb)
    country_of_risk_name = models.CharField(max_length=32, **nb)
    sector = models.CharField(max_length=32, **nb)
    issue_size_plan = models.IntegerField()
    trading_status = models.IntegerField()
    otc_flag = models.BooleanField(default=False)
    buy_available_flag = models.BooleanField(default=False)
    sell_available_flag = models.BooleanField(default=False)
    div_yield_flag = models.BooleanField(default=False)
    share_type = models.IntegerField()
    min_price_increment = models.DecimalField(max_digits=32, decimal_places=16)
    api_trade_available_flag = models.BooleanField(default=False)
    position_uid = models.CharField(max_length=32, **nb)
    for_iis_flag = models.BooleanField(default=False)
    first_1min_candle_date = models.DateTimeField()
    first_1day_candle_date = models.DateTimeField()

    def __str__(self) -> str:
        return f'figi: {self.figi, self.pk}'

    @classmethod
    def bulk_update_or_create(cls, share_list: List[schemas.Share]):
        for share in share_list:
            cls.objects.update_or_create(
                uid=share.uid,
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
                min_price_increment=quotation_to_decimal(share.min_price_increment),
                api_trade_available_flag=share.api_trade_available_flag,
                position_uid=share.position_uid,
                for_iis_flag=share.for_iis_flag,
                first_1min_candle_date=share.first_1min_candle_date,
                first_1day_candle_date=share.first_1day_candle_date
            )

    @classmethod
    def bulk_delete(cls, figi_list: List[str]):
        query = cls.objects.filter(figi__in=figi_list)
        if query.exists():
            query.delete()

    @classmethod
    def get_figi_list(cls):
        return list(cls.objects.values_list('figi', flat=True))

    @classmethod
    async def async_bulk_add_hist_candles(cls, candles: List, figi: str, interval: int):
        share = await cls.objects.aget(figi=figi)

        def _bulk_queryset_generator() -> QuerySet:
            for candle in candles:
                date_time = datetime(
                    year=candle.time.year,
                    month=candle.time.month,
                    day=candle.time.day,
                    tzinfo=tzutc()
                )
                yield HistoricCandle(
                    open_price=quotation_to_decimal(candle.open),
                    close_price=quotation_to_decimal(candle.close),
                    high_price=quotation_to_decimal(candle.high),
                    low_price=quotation_to_decimal(candle.low),
                    volume=candle.volume,
                    date_time=date_time,
                    share=share,
                    interval=interval
                )
        await HistoricCandle.objects.abulk_create(objs=_bulk_queryset_generator())


class HistoricCandle(models.Model):
    open_price = models.DecimalField(max_digits=18, decimal_places=9)
    high_price = models.DecimalField(max_digits=18, decimal_places=9)
    low_price = models.DecimalField(max_digits=18, decimal_places=9)
    close_price = models.DecimalField(max_digits=18, decimal_places=9)
    volume = models.IntegerField()
    date_time = models.DateTimeField()
    share = models.ForeignKey(Share, on_delete=models.CASCADE, db_index=False)
    interval = models.IntegerField()

    def __str__(self) -> str:
        return f"FIGI: {HistoricCandle.share.figi} in interval {HistoricCandle.interval}" \
               f"Open_price: {HistoricCandle.open_price}" \
               f"Close_price: {HistoricCandle.close_price}"

    @classmethod
    def get_candles_by_figi(cls, figi: str) -> QuerySet[HistoricCandle]:
        return cls.objects.filter(share__figi=figi)

    @classmethod
    @sync_to_async()
    def get_last_datetime(cls, figi: str = None) -> Optional[datetime]:
        objects = cls.objects if figi is None else cls.objects.filter(share__figi=figi)
        if objects.exists():
            return objects.latest('date_time').date_time
        return


class MovingAverage(models.Model):
    id = models.BigAutoField(primary_key=True)
    value = models.FloatField()  # TODO may be models.DecimalField(max_digits=32, decimal_places=16)
    figi = models.CharField(max_length=32, **nb)
    date_time = models.DateTimeField()
    period = models.IntegerField()

    @classmethod
    def create(cls, value: float, figi: str, date_time: datetime, period: int):
        cls.objects.update_or_create(
            value=value,
            figi=figi,
            date_time=date_time,
            period=period
        )

    @classmethod
    def get_figi_ma(cls, figi: str = None, period: int = None) -> QuerySet[MovingAverage]:
        if period is None:
            objects = cls.objects if figi is None else cls.objects.filter(figi=figi)
        else:
            objects = cls.objects if figi is None else cls.objects.filter(figi=figi, period=period)
        return objects

    @classmethod
    @sync_to_async()
    def get_last_datetime(cls, period: int = None, figi: str = None) -> Optional[datetime]:
        objects = cls.objects if figi is None else cls.objects.filter(figi=figi)
        if period is not None:
            objects = objects.filter(period=period)
        return max(objects.values_list('date_time', flat=True), default=None)  # TODO SQL SELECT MAX


class Strategy:
    _all_cases = {
        'rsi': 'RSI',
        'sma_50_200': 'cross-SMA 50-200',
        'sma_30_90': 'cross-SMA 30-90',
        'sma_20_60': 'cross-SMA 20-60'
    }

    def __init__(self, strategy_id: str, strategy_name: Optional[str] = None):
        self.strategy_id = strategy_id
        if strategy_name is None:
            self.strategy_name = Strategy._all_cases[strategy_id]
        else:
            self.strategy_name = strategy_name

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
