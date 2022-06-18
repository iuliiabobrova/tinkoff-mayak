# Generated by Django 3.2.13 on 2022-06-18 19:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tgbot', '0008_rename_usersubscriptions_usersubscription'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('strategy_id', models.CharField(blank=True, max_length=32, null=True)),
            ],
            options={
                'ordering': ('-created_at',),
                'abstract': False,
            },
        ),
        migrations.RemoveField(
            model_name='usersubscription',
            name='subscription',
        ),
        migrations.RemoveField(
            model_name='usersubscription',
            name='user',
        ),
        migrations.DeleteModel(
            name='StrategySubscription',
        ),
        migrations.DeleteModel(
            name='UserSubscription',
        ),
        migrations.AddField(
            model_name='user',
            name='subscriptions',
            field=models.ManyToManyField(to='tgbot.Subscription'),
        ),
    ]
