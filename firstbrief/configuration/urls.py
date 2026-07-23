from django.urls import path

from firstbrief.configuration import views

app_name = "configuration"

urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:kind>/new/", views.edit, name="create"),
    path("<slug:kind>/<int:object_id>/", views.edit, name="edit"),
    path("<slug:kind>/<int:object_id>/delete/", views.delete, name="delete"),
]
