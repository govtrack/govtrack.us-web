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
            name='Event',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('source_object_id', models.PositiveIntegerField()),
                ('eventid', models.CharField(max_length=32)),
                ('when', models.DateTimeField(db_index=True)),
                ('seq', models.IntegerField()),
            ],
            options={
                'ordering': ['-id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Feed',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('feedname', models.CharField(max_length=64, db_index=True, unique=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SubscriptionList',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=64)),
                ('is_default', models.BooleanField(default=False)),
                ('email', models.IntegerField(default=0, choices=[(0, b'No Email Updates'), (1, b'Daily'), (2, b'Weekly')])),
                ('last_event_mailed', models.IntegerField(blank=True, null=True)),
                ('last_email_sent', models.DateTimeField(blank=True, null=True)),
                ('public_id', models.CharField(max_length=16, blank=True, null=True, db_index=True)),
                ('trackers', models.ManyToManyField(to='events.Feed', related_name=b'tracked_in_lists')),
                ('user', models.ForeignKey(related_name=b'subscription_lists', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='subscriptionlist',
            unique_together=set([('user', 'name')]),
        ),
        migrations.AddField(
            model_name='event',
            name='feed',
            field=models.ForeignKey(to='events.Feed'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='event',
            name='source_content_type',
            field=models.ForeignKey(to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='event',
            unique_together=set([('source_content_type', 'source_object_id', 'eventid', 'feed'), ('feed', 'id'), ('when', 'source_content_type', 'source_object_id', 'seq', 'feed'), ('feed', 'when', 'source_content_type', 'source_object_id', 'eventid')]),
        ),
    ]
