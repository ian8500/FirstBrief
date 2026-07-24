"""Production settings. Required values are validated by base settings."""

import os

from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault("DJANGO_ENV", "production")

from firstbrief.settings.base import *

if ENVIRONMENT != "production":
    raise ImproperlyConfigured("firstbrief.settings.production requires DJANGO_ENV=production")

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
