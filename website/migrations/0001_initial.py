# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('bill', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignSupporter',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('campaign', models.CharField(max_length=96)),
                ('prefix', models.CharField(max_length=96)),
                ('firstname', models.CharField(max_length=96)),
                ('lastname', models.CharField(max_length=96)),
                ('address', models.CharField(max_length=96)),
                ('city', models.CharField(max_length=96)),
                ('state', models.CharField(max_length=96)),
                ('zipcode', models.CharField(max_length=96)),
                ('email', models.CharField(max_length=96)),
                ('message', models.CharField(max_length=256, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('district', models.IntegerField(blank=True, null=True)),
                ('geocode_response', models.TextField(blank=True, null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CommunityInterest',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('methods', models.CharField(max_length=32)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('bill', models.ForeignKey(to='bill.Bill')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MediumPost',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('medium_id', models.CharField(max_length=32, unique=True)),
                ('title', models.CharField(max_length=128)),
                ('collection_slug', models.CharField(max_length=128)),
                ('post_slug', models.CharField(max_length=128)),
                ('data', jsonfield.fields.JSONField(default={})),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('published', models.DateTimeField(db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PayPalPayment',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('paypal_id', models.CharField(max_length=64, db_index=True)),
                ('response_data', jsonfield.fields.JSONField()),
                ('executed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('notes', models.CharField(max_length=64)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('subject', models.CharField(max_length=20, db_index=True)),
                ('anon_session_key', models.CharField(max_length=64, blank=True, null=True, db_index=True)),
                ('reaction', jsonfield.fields.JSONField()),
                ('extra', jsonfield.fields.JSONField()),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Req',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('request', models.TextField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Sousveillance',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('subject', models.CharField(max_length=24, db_index=True)),
                ('req', jsonfield.fields.JSONField()),
                ('when', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('massemail', models.BooleanField(default=True)),
                ('old_id', models.IntegerField(blank=True, null=True)),
                ('last_mass_email', models.IntegerField(default=0)),
                ('congressionaldistrict', models.CharField(max_length=4, blank=True, null=True, db_index=True)),
                ('paid_features', jsonfield.fields.JSONField(default={}, blank=True, null=True)),
                ('one_click_unsub_key', models.CharField(unique=True, max_length=64, blank=True, null=True, db_index=True)),
                ('one_click_unsub_gendate', models.DateTimeField(blank=True, null=True)),
                ('one_click_unsub_hit', models.DateTimeField(blank=True, null=True)),
                ('research_anon_key', models.IntegerField(blank=True, null=True, unique=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, unique=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='reaction',
            unique_together=set([('subject', 'anon_session_key'), ('subject', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='paypalpayment',
            unique_together=set([('user', 'created')]),
        ),
        migrations.AlterUniqueTogether(
            name='communityinterest',
            unique_together=set([('user', 'bill')]),
        ),
    ]
