"""Root URL configuration."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from firstbrief.core import views

handler400 = "firstbrief.core.error_views.bad_request"
handler403 = "firstbrief.core.error_views.permission_denied"
handler404 = "firstbrief.core.error_views.page_not_found"
handler500 = "firstbrief.core.error_views.server_error"

urlpatterns = [
    path("", views.home, name="home"),
    path("access/", include("firstbrief.identity.urls")),
    path("configuration/", include("firstbrief.configuration.urls")),
    path("admin/", admin.site.urls),
    path("health/live/", views.liveness, name="health-live"),
    path("health/ready/", views.readiness, name="health-ready"),
]
