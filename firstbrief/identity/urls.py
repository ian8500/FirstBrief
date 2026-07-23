from django.contrib.auth.views import PasswordChangeDoneView
from django.urls import path

from firstbrief.identity import views

app_name = "identity"

urlpatterns = [
    path("login/", views.FirstBriefLoginView.as_view(), name="login"),
    path("logout/", views.logout_confirm, name="logout"),
    path("profile/", views.profile, name="profile"),
    path(
        "password/change/",
        views.FirstBriefPasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "password/change/done/",
        PasswordChangeDoneView.as_view(template_name="identity/password_change_done.html"),
        name="password-change-done",
    ),
    path(
        "password/reset/",
        views.FirstBriefPasswordResetView.as_view(),
        name="password-reset",
    ),
    path("password/reset/done/", views.password_reset_done, name="password-reset-done"),
    path(
        "password/reset/<uidb64>/<token>/",
        views.FirstBriefPasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/reset/complete/",
        views.password_reset_complete,
        name="password-reset-complete",
    ),
    path("users/", views.user_list, name="user-list"),
    path("users/create/", views.user_create, name="user-create"),
    path("users/<int:user_id>/reset/", views.user_reset_password, name="user-reset"),
    path("users/temporary-password/", views.one_time_password, name="one-time-password"),
]
