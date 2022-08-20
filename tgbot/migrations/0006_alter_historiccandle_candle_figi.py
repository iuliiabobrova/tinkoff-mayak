# Generated by Django 4.1 on 2022-08-19 13:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tgbot', '0005_rename_figi_historiccandle_candle_figi'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historiccandle',
            name='candle_figi',
            field=models.ForeignKey(db_index=False, on_delete=django.db.models.deletion.CASCADE, related_name='candles', to='tgbot.share'),
        ),
    ]