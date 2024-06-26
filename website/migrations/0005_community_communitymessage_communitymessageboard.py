# Generated by Django 2.2.24 on 2021-07-05 17:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('website', '0004_userprofile_inactivity_warning_sent'),
    ]

    operations = [
        migrations.CreateModel(
            name='Community',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField()),
                ('name', models.CharField(help_text='The display name of the community.', max_length=256)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('access_explanation', models.TextField(help_text='Displayed below the post form to let the user know who can read the post.')),
                ('login_teaser', models.TextField(help_text='Teaser text to get an anonymous user to log in to post. Applicable if the community is based on an IP-range.')),
                ('post_teaser', models.TextField(help_text='Teaser text to get a logged in user to open the post form.')),
                ('author_display_field_label', models.TextField(help_text="The text to use for the form field label for the author_display field, which is a signature line for the author, recognizing that a person's name, title, and organization can change over time without a change in user account or email address.")),
            ],
            options={
                'verbose_name_plural': 'Communities',
            },
        ),
        migrations.CreateModel(
            name='CommunityMessageBoard',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(db_index=True, help_text='A code for the topic of the board, i.e. where the board appears on the website.', max_length=20)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('community', models.ForeignKey(help_text='The community that has acccess to read and post to this board.', on_delete=django.db.models.deletion.PROTECT, to='website.Community')),
            ],
        ),
        migrations.CreateModel(
            name='CommunityMessage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('author_display', models.TextField(help_text="A signature line for the author, recognizing that a person's name, title, and organization can change over time without a change in user account or email address.")),
                ('message', models.TextField()),
                ('history', jsonfield.fields.JSONField(help_text='The history of edits to this post as a list of dicts holding previous field values.')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('board', models.ForeignKey(help_text='The board that this message is a part of.', on_delete=django.db.models.deletion.PROTECT, to='website.CommunityMessageBoard')),
            ],
            options={
                'index_together': {('board', 'modified')},
            },
        ),
    ]
