# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('website', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('subject', models.CharField(max_length=20, db_index=True)),
                ('anon_session_key', models.CharField(max_length=64, db_index=True, blank=True, null=True)),
                ('position', models.IntegerField(null=True, blank=True)),
                ('reasons', models.TextField(blank=True)),
                ('extra', jsonfield.fields.JSONField()),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='position',
            unique_together=set([('subject', 'user'), ('subject', 'anon_session_key')]),
        ),
    ]
