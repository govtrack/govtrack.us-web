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
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CallLog',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('status', models.CharField(max_length=64)),
                ('log', jsonfield.fields.JSONField(help_text=b'A dict of TwilML information for different parts of the call.')),
            ],
            options={
                'ordering': ('-created',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Issue',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('slug', models.SlugField(help_text=b'The slug for this issue in URLs.')),
                ('title', models.CharField(help_text=b"The issue's display title.", max_length=255)),
                ('question', models.CharField(help_text=b'The issue phrased as a question.', max_length=255)),
                ('introtext', models.TextField(help_text=b'Text introducing the issue.')),
                ('created', models.DateTimeField(help_text=b'The date and time the issue was created.', db_index=True, auto_now_add=True)),
                ('isopen', models.BooleanField(help_text=b'Whether users can currently participate in this issue.', default=False, verbose_name=b'Open')),
            ],
            options={
                'ordering': ('-created',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IssuePosition',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('text', models.CharField(help_text=b'A description of the position.', max_length=255)),
                ('valence', models.NullBooleanField(help_text=b'The valence of this position, for linking with bills.')),
                ('created', models.DateTimeField(help_text=b'The date and time the issue was created.', db_index=True, auto_now_add=True)),
                ('call_script', models.TextField(help_text=b'What you should say when you call your rep about this issue.', blank=True, null=True)),
            ],
            options={
                'ordering': ('-created',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RelatedBill',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('valence', models.NullBooleanField(help_text=b'The valence of this bill, for linking with IssuePositions. If not null, a user who supports this bill takes the position of the IssuePosition with the same valence value.')),
                ('bill', models.ForeignKey(help_text=b'The related bill.', on_delete=django.db.models.deletion.PROTECT, to='bill.Bill')),
                ('issue', models.ForeignKey(help_text=b'The related issue.', related_name=b'bills', to='poll_and_call.Issue')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserPosition',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('district', models.CharField(help_text=b'The state and district, in uppercase without any spaces, of the user at the time the user took this posiiton.', max_length=4, db_index=True)),
                ('metadata', jsonfield.fields.JSONField(help_text=b'Other information stored with the position.')),
                ('position', models.ForeignKey(help_text=b'The position the user choses.', to='poll_and_call.IssuePosition')),
                ('user', models.ForeignKey(help_text=b'The user who created this position.', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='issue',
            name='positions',
            field=models.ManyToManyField(help_text=b'The positions associated with this issue.', to='poll_and_call.IssuePosition', db_index=True, related_name=b'issue'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='calllog',
            name='position',
            field=models.ForeignKey(help_text=b'The position this call was communicating.', to='poll_and_call.UserPosition'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='calllog',
            name='target',
            field=models.ForeignKey(help_text=b'The Member of Congress the user called.', on_delete=django.db.models.deletion.PROTECT, to='person.PersonRole'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='calllog',
            name='user',
            field=models.ForeignKey(help_text=b'The user who created this call.', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
