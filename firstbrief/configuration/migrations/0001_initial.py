import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []
    operations = [
        migrations.CreateModel(
            name="MessageType",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Site",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="PrimaryMessageGroup",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="primary_groups",
                        to="configuration.site",
                    ),
                ),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="MessageGroup",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "primary_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="message_groups",
                        to="configuration.primarymessagegroup",
                    ),
                ),
            ],
            options={"ordering": ("name",)},
        ),
    ]
