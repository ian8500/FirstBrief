from django.urls import path

from firstbrief.sapimport import views

app_name = "sapimport"

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload, name="upload"),
    path("<uuid:batch_id>/", views.review, name="review"),
    path("<uuid:batch_id>/commit/", views.commit, name="commit"),
]
