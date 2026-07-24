from __future__ import annotations

import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("messaging", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OperationalPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                (
                    "pre_effective_hours",
                    models.PositiveSmallIntegerField(
                        default=24,
                        help_text=("Hours before effective time that forthcoming messages appear."),
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(720),
                        ],
                    ),
                ),
                (
                    "pre_effective_colour",
                    models.CharField(
                        default="#6f42c1",
                        help_text=(
                            "A text label and icon are also shown; colour is never the only cue."
                        ),
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                message=("Enter a six-digit hexadecimal colour such as #6f42c1."),
                                regex="^#[0-9A-Fa-f]{6}$",
                            )
                        ],
                    ),
                ),
                (
                    "idle_timeout_seconds",
                    models.PositiveSmallIntegerField(
                        default=60,
                        help_text=("Viewing time pauses after this many seconds without activity."),
                        validators=[
                            django.core.validators.MinValueValidator(15),
                            django.core.validators.MaxValueValidator(900),
                        ],
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MessageReceipt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("first_read_at", models.DateTimeField(blank=True, null=True)),
                ("cleared_at", models.DateTimeField(blank=True, null=True)),
                ("cumulative_view_seconds", models.PositiveIntegerField(default=0)),
                ("printed_at", models.DateTimeField(blank=True, null=True)),
                ("emailed_at", models.DateTimeField(blank=True, null=True)),
                ("last_accessed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="receipts",
                        to="messaging.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="message_receipts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["user", "cleared_at"],
                        name="receipt_user_cleared",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "message"),
                        name="unique_user_message_receipt",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MessageViewSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("browser_session_key", models.CharField(blank=True, max_length=40)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("active_seconds", models.PositiveIntegerField(default=0)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="view_sessions",
                        to="messaging.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="message_view_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MessageAccessEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("opened", "Opened"),
                            ("read", "Read"),
                            ("cleared", "Read and cleared"),
                            ("printed", "Printed"),
                            ("emailed", "Emailed to self"),
                            ("feedback", "Feedback sent"),
                        ],
                        max_length=16,
                    ),
                ),
                ("browser_session_key", models.CharField(blank=True, max_length=40)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="access_events",
                        to="messaging.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="message_access_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("occurred_at", "pk"),
                "indexes": [
                    models.Index(
                        fields=["user", "message", "occurred_at"],
                        name="access_user_message_time",
                    )
                ],
            },
        ),
    ]
