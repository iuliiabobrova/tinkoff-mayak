# Generated by Django 4.1 on 2022-08-19 12:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tgbot', '0004_alter_historiccandle_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='historiccandle',
            old_name='figi',
            new_name='candle_figi',
        ),
    ]
