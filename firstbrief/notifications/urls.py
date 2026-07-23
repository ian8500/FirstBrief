from django.urls import path

from firstbrief.notifications import views

app_name = "notifications"

urlpatterns = [
    path("manage/", views.operations, name="operations"),
    path("manage/<int:job_pk>/resend/", views.resend, name="resend"),
]
