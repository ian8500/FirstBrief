"""Production settings. Required values are validated by base settings."""

import os

from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault("DJANGO_ENV", "production")

from firstbrief.settings.base import *

if ENVIRONMENT != "production":
    raise ImproperlyConfigured("firstbrief.settings.production requires DJANGO_ENV=production")

DEBUG = False
