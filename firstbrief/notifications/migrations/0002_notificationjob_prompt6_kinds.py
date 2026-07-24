from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationjob",
            name="kind",
            field=models.CharField(
                choices=[
                    ("created", "Message created"),
                    ("approved", "Message approved"),
                    ("unapproved_effective", "Unapproved at effective time"),
                    ("manual_resend", "Manual resend"),
                    ("message_to_self", "Message emailed to user"),
                    ("feedback", "Message feedback"),
                ],
                max_length=24,
            ),
        ),
    ]
