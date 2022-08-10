from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render

from dtb.settings import DEBUG

from tgbot.models import (
    User,
    FeedbackMessage,
    Subscription,
    Command,
    HistoricCandle,
    Share,
    MovingAverage
)
from tgbot.forms import BroadcastForm

from tgbot.tasks import broadcast_message
from tgbot.handlers.broadcast_message.utils import send_message


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        'user_id', 'username', 'first_name', 'last_name',
        'language_code', 'deep_link',
        'created_at', 'updated_at', "is_blocked_bot",
    ]
    list_filter = ["is_blocked_bot", ]
    search_fields = ('username', 'user_id')

    actions = ['broadcast', 'save_csv']

    def save_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            row = writer.writerow([getattr(obj, field) for field in field_names])
        return response

    def broadcast(self, request, queryset):
        """ Select users via check mark in django-admin panel, then select "Broadcast" to send message"""
        user_ids = queryset.values_list(
            'user_id', flat=True).distinct().iterator()
        if 'apply' in request.POST:
            broadcast_message_text = request.POST["broadcast_text"]

            if DEBUG:  # for test / debug purposes - run in same thread
                for user_id in user_ids:
                    send_message(user_id=user_id, text=broadcast_message_text)
                self.message_user(
                    request, f"Just broadcasted to {len(queryset)} users")
            else:
                broadcast_message.delay(
                    text=broadcast_message_text, user_ids=list(user_ids))
                self.message_user(
                    request, f"Broadcasting of {len(queryset)} messages has been started")

            return HttpResponseRedirect(request.get_full_path())
        else:
            form = BroadcastForm(initial={'_selected_action': user_ids})
            return render(
                request, "admin/broadcast_message.html", {
                    'form': form, 'title': u'Broadcast message'}
            )


class UserInline(admin.TabularInline):
    model = User.subscriptions.through


@admin.register(FeedbackMessage)
class FeedbackMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'update_id', 'text', 'user_id', 'user', 'created_at']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    model = Subscription
    inlines = [
        UserInline
    ]
    list_display = ['id', 'strategy_id', 'created_at']
    actions = ['broadcast', 'save_csv']

    def save_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            row = writer.writerow([getattr(obj, field) for field in field_names])
        return response


@admin.register(Command)
class CommandAdmin(admin.ModelAdmin):
    list_display = ['command_id', 'command_name',
                    'user_id', 'username', 'created_at']
    actions = ['broadcast', 'save_csv']

    def save_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            row = writer.writerow([getattr(obj, field) for field in field_names])
        return response


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = [
        'uid',
        'figi',
        'ticker',
        'class_code',
        'isin',
        'lot',
        'currency',
        'klong',
        'kshort',
        'dlong',
        'dshort',
        'dlong_min',
        'dshort_min',
        'short_enabled_flag',
        'name',
        'exchange',
        'ipo_date',
        'issue_size',
        'country_of_risk',
        'country_of_risk_name',
        'sector',
        'issue_size_plan',
        'trading_status',
        'otc_flag',
        'buy_available_flag',
        'sell_available_flag',
        'div_yield_flag',
        'share_type',
        'min_price_increment',
        'api_trade_available_flag',
        'position_uid',
        'for_iis_flag',
        'first_1min_candle_date',
    ]


@admin.register(HistoricCandle)
class HistoricCandleAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'open_price',
        'high_price',
        'low_price',
        'close_price',
        'volume',
        'date_time',
        'figi',
        'interval'
    ]


@admin.register(MovingAverage)
class MovingAverageAdmin(admin.ModelAdmin):
    list_display = [
        'value',
        'figi',
        'date_time',
        'period'
    ]
