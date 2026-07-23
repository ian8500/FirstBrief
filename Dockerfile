FROM python:3.12.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system firstbrief \
    && useradd --system --gid firstbrief --home-dir /app firstbrief

COPY requirements/base.txt requirements/base.txt
RUN python -m pip install --upgrade pip==26.1.2 \
    && python -m pip install --requirement requirements/base.txt

COPY --chown=firstbrief:firstbrief . .
RUN DJANGO_SETTINGS_MODULE=firstbrief.settings.development \
    DJANGO_ENV=development \
    python manage.py collectstatic --noinput \
    && chown -R firstbrief:firstbrief /app

USER firstbrief

FROM runtime AS development

USER root
RUN python -m pip install --requirement requirements/dev.txt
USER firstbrief

ENV DJANGO_SETTINGS_MODULE=firstbrief.settings.development \
    DJANGO_ENV=development

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM runtime AS production

ENV DJANGO_SETTINGS_MODULE=firstbrief.settings.production \
    DJANGO_ENV=production

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live/', timeout=3)"]

CMD ["gunicorn", "firstbrief.wsgi:application", "--bind=0.0.0.0:8000", "--workers=3", "--access-logfile=-", "--error-logfile=-"]
