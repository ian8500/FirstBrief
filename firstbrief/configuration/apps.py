from django.apps import AppConfig


class ConfigurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "firstbrief.configuration"

    def ready(self) -> None:
        from firstbrief.configuration import signals  # noqa: F401
