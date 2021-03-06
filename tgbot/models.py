from __future__ import annotations

from typing import Union, Optional, Tuple, List

from django.db import models
from django.db.models import QuerySet, Manager
from numpy import number
from telegram import Update
from telegram.ext import CallbackContext

from dtb.settings import DEBUG
from tgbot.handlers.utils.info import extract_user_data_from_update
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

    # ?????? ?????????????? ?????????????????? ?????????????? ???????????? user_id - id ???????????????? ???? ??????????????????
    # ?? ?????????????? ?????????????? ?????????????????? ?????????? ?????????????????? ??????????????????
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
        # TODO: ???????????????? ???? ??????????????????????, ???????? ???????????????? ?????????????????? ????????????????
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

    def __str__(self):
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
