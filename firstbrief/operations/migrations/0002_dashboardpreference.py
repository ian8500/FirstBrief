import django.db.models.deletion
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("show_forthcoming", models.BooleanField(default=True)),
                ("show_botd", models.BooleanField(default=True)),
                ("show_approvals", models.BooleanField(default=True)),
                ("show_returned_drafts", models.BooleanField(default=True)),
                ("show_notification_failures", models.BooleanField(default=True)),
                ("show_expiring_instructions", models.BooleanField(default=True)),
                ("show_recently_opened", models.BooleanField(default=True)),
                (
                    "item_limit",
                    models.PositiveSmallIntegerField(
                        choices=[(5, "5 items"), (10, "10 items"), (20, "20 items")],
                        default=10,
                    ),
                ),
                (
                    "expiring_within_days",
                    models.PositiveSmallIntegerField(
                        default=7,
                        help_text="Show authorised instructions expiring within this many days.",
                        validators=[MinValueValidator(1), MaxValueValidator(30)],
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_preference",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
