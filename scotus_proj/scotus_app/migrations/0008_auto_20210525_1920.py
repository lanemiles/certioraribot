# Generated by Django 3.2.3 on 2021-05-25 19:20

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("scotus_app", "0007_case_question_presented"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="case",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
