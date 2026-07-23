"""FirstBrief application package."""

from firstbrief.celery import app as celery_app

__all__ = ("celery_app",)
