# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('bill', '0001_initial'),
        ('person', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WhipReport',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('report_type', models.IntegerField(help_text=b'The nature of the report being made.', choices=[(2, b'Cited Source'), (3, b'Phone Call'), (1, b'Self Report')])),
                ('report_result', models.IntegerField(help_text=b'The information gleaned by this report.', default=0, choices=[(1, b'Not Entered'), (0, b'Invalid'), (8, b'Asked To Call Back'), (4, b'Member Supports The Bill'), (6, b"It's Complicated"), (2, b'No Information Found'), (3, b'Member Has No Position'), (5, b'Member Opposes The Bill'), (7, b'Got Voicemail')])),
                ('review_status', models.IntegerField(help_text=b'The information gleaned by this report.', default=0, choices=[(2, b'Bad'), (0, b'Not Reviewed'), (1, b'OK')])),
                ('citation_url', models.CharField(max_length=256, blank=True, null=True)),
                ('citation_title', models.CharField(max_length=256, blank=True, null=True)),
                ('citation_date', models.DateField(help_text=b'The date on which the reported information was valid, if different from the creation date of this report.', blank=True, null=True)),
                ('created', models.DateTimeField(help_text=b'The date and time the report was filed.', db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(help_text=b'The date and time the report was filed.', auto_now=True)),
                ('call_status', models.CharField(max_length=64, blank=True, null=True)),
                ('call_log', jsonfield.fields.JSONField(help_text=b'A dict of TwilML information for different parts of the call.', blank=True, null=True)),
                ('bill', models.ForeignKey(help_text=b'The bill the call was about.', on_delete=django.db.models.deletion.PROTECT, to='bill.Bill')),
                ('target', models.ForeignKey(help_text=b'The Member of Congress called.', on_delete=django.db.models.deletion.PROTECT, to='person.PersonRole')),
                ('user', models.ForeignKey(help_text=b'The user making the phone call or reporting the information.', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created',),
            },
            bases=(models.Model,),
        ),
    ]
