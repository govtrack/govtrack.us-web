# Generated by Django 2.2.28 on 2024-04-25 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0010_auto_20240411_1503'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='massemail_options',
            field=models.CharField(default='', max_length=128),
        ),
    ]