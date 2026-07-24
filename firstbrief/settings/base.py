"""Shared settings for all FirstBrief environments."""

from __future__ import annotations

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ENV=(str, "production"),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_SECURE_SSL_REDIRECT=(bool, True),
    FIRSTBRIEF_SITE_TIMEZONE=(str, "Europe/London"),
    LOG_LEVEL=(str, "INFO"),
    FIRSTBRIEF_LOCAL_AUTH_ENABLED=(bool, False),
    FIRSTBRIEF_MALWARE_SCANNER=(str, "firstbrief.messaging.scanning.UnavailableScanner"),
)

if env.bool("DJANGO_READ_DOT_ENV", default=False):
    environ.Env.read_env(BASE_DIR / ".env")

ENVIRONMENT = env("DJANGO_ENV")
DEBUG = env("DJANGO_DEBUG")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY:
    if ENVIRONMENT in {"development", "test"}:
        SECRET_KEY = "firstbrief-development-only-insecure-secret-key"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required outside development/test")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS and ENVIRONMENT not in {"development", "test"}:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required outside development/test")

CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")
SITE_TIME_ZONE = env("FIRSTBRIEF_SITE_TIMEZONE")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "firstbrief.assurance",
    "firstbrief.configuration",
    "firstbrief.core",
    "firstbrief.identity",
    "firstbrief.messaging",
    "firstbrief.notifications",
    "firstbrief.operations",
    "firstbrief.retrieval",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "firstbrief.core.middleware.CorrelationIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "firstbrief.identity.middleware.IdentitySessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "firstbrief.core.middleware.BaselineSecurityHeadersMiddleware",
]

AUTH_USER_MODEL = "identity.User"

EXTERNAL_AUTH_BACKEND = env("FIRSTBRIEF_EXTERNAL_AUTH_BACKEND", default="")
LOCAL_AUTH_ENABLED = env("FIRSTBRIEF_LOCAL_AUTH_ENABLED")
if ENVIRONMENT in {"development", "test"}:
    LOCAL_AUTH_ENABLED = env.bool("FIRSTBRIEF_LOCAL_AUTH_ENABLED", default=True)
if ENVIRONMENT == "production" and not (EXTERNAL_AUTH_BACKEND or LOCAL_AUTH_ENABLED):
    raise ImproperlyConfigured(
        "Configure FIRSTBRIEF_EXTERNAL_AUTH_BACKEND or explicitly enable local auth"
    )
AUTHENTICATION_BACKENDS = [
    backend
    for backend in (
        EXTERNAL_AUTH_BACKEND,
        "firstbrief.identity.backends.LocalAccountBackend" if LOCAL_AUTH_ENABLED else "",
    )
    if backend
]

ROOT_URLCONF = "firstbrief.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "firstbrief.configuration.context_processors.configuration_access",
                "firstbrief.messaging.context_processors.message_access",
                "firstbrief.notifications.context_processors.notification_access",
            ],
        },
    },
]

WSGI_APPLICATION = "firstbrief.wsgi.application"
ASGI_APPLICATION = "firstbrief.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

CACHES = {
    "default": env.cache(
        "CACHE_URL",
        default="locmemcache://",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "firstbrief.identity.validators.FirstBriefPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
PASSWORD_RESET_TIMEOUT = env.int("FIRSTBRIEF_PASSWORD_RESET_TIMEOUT", default=1_800)
LOGIN_URL = "identity:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "identity:login"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
FIRSTBRIEF_MALWARE_SCANNER = env("FIRSTBRIEF_MALWARE_SCANNER")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env("DJANGO_SECURE_SSL_REDIRECT")
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env.int("DJANGO_SESSION_COOKIE_AGE", default=1_800)
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

DATA_UPLOAD_MAX_MEMORY_SIZE = env.int(
    "DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=2_621_440,
)
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int(
    "DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE",
    default=2_621_440,
)

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="firstbrief@example.invalid")

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "firstbrief-process-outbox": {
        "task": "firstbrief.notifications.process_outbox",
        "schedule": 60.0,
    },
    "firstbrief-process-lifecycle": {
        "task": "firstbrief.notifications.process_lifecycle",
        "schedule": 60.0,
    },
    "firstbrief-deliver-notifications": {
        "task": "firstbrief.notifications.deliver",
        "schedule": 60.0,
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "firstbrief.core.logging.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL"),
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL"),
            "propagate": False,
        },
    },
}
