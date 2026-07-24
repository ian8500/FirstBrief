from django.urls import path

from firstbrief.operations import views

app_name = "operations"

urlpatterns = [
    path("mandatory/", views.message_list, {"list_kind": "mandatory"}, name="mandatory"),
    path("other/", views.message_list, {"list_kind": "other"}, name="other"),
    path("messages/<uuid:message_pk>/", views.message_viewer, name="viewer"),
    path("messages/<uuid:message_pk>/close/", views.close_message, name="close"),
    path("messages/<uuid:message_pk>/print/", views.print_message, name="print"),
    path("messages/<uuid:message_pk>/email/", views.email_message, name="email"),
    path("messages/<uuid:message_pk>/feedback/", views.feedback, name="feedback"),
    path(
        "messages/<uuid:message_pk>/files/<uuid:asset_pk>/",
        views.protected_file,
        name="file",
    ),
    path("settings/", views.settings_view, name="settings"),
]
