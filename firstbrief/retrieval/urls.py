from django.urls import path

from firstbrief.retrieval import views

app_name = "retrieval"

urlpatterns = [
    path("", views.search, name="search"),
    path("export.csv", views.export_csv, name="export"),
    path("suggest/messages/", views.suggest_messages, name="suggest-messages"),
    path("suggest/users/", views.suggest_users, name="suggest-users"),
    path("messages/<uuid:message_pk>/", views.message_detail, name="message"),
    path(
        "messages/<uuid:message_pk>/files/<uuid:asset_pk>/",
        views.protected_file,
        name="file",
    ),
]
