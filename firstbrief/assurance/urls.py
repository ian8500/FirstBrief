from django.urls import path

from firstbrief.assurance import views

app_name = "assurance"

urlpatterns = [
    path("", views.audit, name="audit"),
    path("retention/", views.retention, name="retention"),
    path("retention/<uuid:run_id>/approve/", views.approve_purge, name="approve-purge"),
    path("continuity.json", views.continuity, name="continuity"),
]
