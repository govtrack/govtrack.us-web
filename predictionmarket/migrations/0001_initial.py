# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Market',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('owner_object_id', models.PositiveIntegerField()),
                ('owner_key', models.CharField(max_length=16)),
                ('name', models.CharField(max_length=128)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('volatility', models.FloatField(default=5.0)),
                ('volume', models.IntegerField(default=0)),
                ('tradecount', models.IntegerField(default=0, db_index=True)),
                ('isopen', models.BooleanField(default=True)),
                ('owner_content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Outcome',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('owner_key', models.CharField(max_length=16)),
                ('name', models.CharField(max_length=128)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('volume', models.IntegerField(default=0)),
                ('tradecount', models.IntegerField(default=0, db_index=True)),
                ('market', models.ForeignKey(related_name=b'outcomes', to='predictionmarket.Market')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Trade',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('shares', models.IntegerField()),
                ('value', models.FloatField()),
                ('liquidation', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TradingAccount',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('balance', models.FloatField(default=0)),
                ('user', models.OneToOneField(related_name=b'tradingaccount', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='trade',
            name='account',
            field=models.ForeignKey(related_name=b'trades', to='predictionmarket.TradingAccount'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='trade',
            name='outcome',
            field=models.ForeignKey(related_name=b'trades', to='predictionmarket.Outcome'),
            preserve_default=True,
        ),
    ]
