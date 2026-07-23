from django.urls import path

from firstbrief.messaging import views

app_name = "messaging"

urlpatterns = [
    path("manage/", views.message_list, name="list"),
    path("manage/new/", views.message_create, name="create"),
    path("manage/<uuid:message_pk>/", views.message_detail, name="detail"),
    path("manage/<uuid:message_pk>/edit/", views.message_edit, name="edit"),
    path(
        "manage/<uuid:message_pk>/<slug:command>/",
        views.message_action,
        name="action",
    ),
]
