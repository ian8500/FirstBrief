import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("configuration", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="Capability",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("codename", models.SlugField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=160)),
            ],
            options={"ordering": ("codename",)},
        ),
        migrations.CreateModel(
            name="IdentityPolicy",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                (
                    "max_failed_logins",
                    models.PositiveSmallIntegerField(
                        default=5,
                        validators=[django.core.validators.MinValueValidator(2)],
                    ),
                ),
                (
                    "lockout_minutes",
                    models.PositiveSmallIntegerField(
                        default=30,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "session_timeout_minutes",
                    models.PositiveSmallIntegerField(
                        default=30,
                        validators=[django.core.validators.MinValueValidator(5)],
                    ),
                ),
                (
                    "password_expiry_days",
                    models.PositiveSmallIntegerField(
                        default=90,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("password_warning_days", models.PositiveSmallIntegerField(default=14)),
                (
                    "password_min_length",
                    models.PositiveSmallIntegerField(
                        default=12,
                        validators=[django.core.validators.MinValueValidator(12)],
                    ),
                ),
                (
                    "password_max_length",
                    models.PositiveSmallIntegerField(
                        default=128,
                        validators=[django.core.validators.MinValueValidator(64)],
                    ),
                ),
                ("approval_notification_email", models.EmailField(blank=True)),
                ("policy_notification_email", models.EmailField(blank=True)),
                ("account_lock_distribution_list", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "capabilities",
                    models.ManyToManyField(
                        blank=True,
                        related_name="roles",
                        to="identity.capability",
                    ),
                ),
                (
                    "message_types",
                    models.ManyToManyField(
                        blank=True,
                        related_name="roles",
                        to="configuration.messagetype",
                    ),
                ),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True)),
                ("is_superuser", models.BooleanField(default=False)),
                (
                    "username",
                    models.CharField(
                        max_length=150,
                        unique=True,
                        validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    ),
                ),
                ("first_name", models.CharField(blank=True, max_length=150)),
                ("last_name", models.CharField(blank=True, max_length=150)),
                ("email", models.EmailField(blank=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now)),
                ("include_in_reports", models.BooleanField(default=True)),
                ("imported_from_sap", models.BooleanField(default=False)),
                ("must_change_password", models.BooleanField(default=False)),
                ("password_changed_at", models.DateTimeField(blank=True, null=True)),
                ("failed_login_count", models.PositiveIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("local_auth_enabled", models.BooleanField(default=True)),
                (
                    "default_message_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="default_for_users",
                        to="configuration.messagegroup",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="users",
                        to="configuration.site",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(blank=True, related_name="user_set", to="auth.group"),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        related_name="user_set",
                        to="auth.permission",
                    ),
                ),
                (
                    "message_groups",
                    models.ManyToManyField(
                        blank=True,
                        related_name="users",
                        to="configuration.messagegroup",
                    ),
                ),
                (
                    "direct_capabilities",
                    models.ManyToManyField(
                        blank=True,
                        related_name="direct_users",
                        to="identity.capability",
                    ),
                ),
                (
                    "roles",
                    models.ManyToManyField(blank=True, related_name="users", to="identity.role"),
                ),
            ],
            managers=[("objects", django.contrib.auth.models.UserManager())],
        ),
        migrations.CreateModel(
            name="SupervisorRelationship",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                (
                    "reportee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supervisors",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "supervisor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reportees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_default", True)),
                fields=("is_default",),
                name="one_default_identity_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="supervisorrelationship",
            constraint=models.UniqueConstraint(
                fields=("supervisor", "reportee", "starts_at"),
                name="unique_supervisor_period",
            ),
        ),
    ]
