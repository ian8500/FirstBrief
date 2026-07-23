from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []
    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("action", models.CharField(db_index=True, max_length=100)),
                ("object_type", models.CharField(max_length=100)),
                ("object_id", models.CharField(blank=True, max_length=100)),
                ("occurred_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("correlation_id", models.CharField(blank=True, max_length=128)),
                ("reason", models.TextField(blank=True)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ("-occurred_at", "-pk")},
        )
    ]
