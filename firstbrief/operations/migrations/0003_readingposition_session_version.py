import django.db.models.deletion
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0001_initial"),
        ("operations", "0002_dashboardpreference"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="messageviewsession",
            name="version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="view_sessions",
                to="messaging.messageversion",
            ),
        ),
        migrations.AddField(
            model_name="messageviewsession",
            name="mandatory_at_open",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="ReadingPosition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("page", models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])),
                (
                    "total_pages",
                    models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)]),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reading_positions",
                        to="messaging.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reading_positions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reading_positions",
                        to="messaging.messageversion",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["user", "message", "version"],
                        name="reading_position_lookup",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "message", "version"),
                        name="unique_user_message_version_position",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("page__lte", models.F("total_pages"))),
                        name="reading_page_within_total",
                    ),
                ],
            },
        ),
        migrations.AlterField(
            model_name="messageaccessevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("opened", "Opened"),
                    ("read", "Read"),
                    ("acknowledged", "Acknowledged"),
                    ("cleared", "Read and cleared"),
                    ("printed", "Printed"),
                    ("emailed", "Emailed to self"),
                    ("feedback", "Feedback sent"),
                ],
                max_length=16,
            ),
        ),
    ]
