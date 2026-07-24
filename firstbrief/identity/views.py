from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from firstbrief.assurance.services import record_event
from firstbrief.identity.forms import (
    AccessibleAuthenticationForm,
    LocalPasswordChangeForm,
    LocalResetConfirmForm,
    UserCreateForm,
)
from firstbrief.identity.models import User
from firstbrief.identity.services import (
    MANAGE_USERS,
    has_capability,
    provision_local_user,
    reset_local_password,
    visible_users_for,
)


def authenticated_user(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise PermissionDenied
    return request.user


class FirstBriefLoginView(LoginView):
    template_name = "identity/login.html"
    authentication_form = AccessibleAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form: AuthenticationForm) -> HttpResponse:
        previous_login = form.get_user().last_login
        response = super().form_valid(form)
        if previous_login is not None:
            self.request.session["previous_login_at"] = previous_login.isoformat()
        return response


class FirstBriefPasswordChangeView(PasswordChangeView):
    template_name = "identity/password_change.html"
    form_class = LocalPasswordChangeForm
    success_url = reverse_lazy("identity:password-change-done")

    def form_valid(self, form: LocalPasswordChangeForm) -> HttpResponse:
        response = super().form_valid(form)
        user = authenticated_user(self.request)
        record_event("identity.password.changed", actor=user, subject=user)
        return response


class FirstBriefPasswordResetView(PasswordResetView):
    template_name = "identity/password_reset.html"
    email_template_name = "identity/password_reset_email.txt"
    subject_template_name = "identity/password_reset_subject.txt"
    success_url = reverse_lazy("identity:password-reset-done")


class FirstBriefPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "identity/password_reset_confirm.html"
    form_class = LocalResetConfirmForm
    success_url = reverse_lazy("identity:password-reset-complete")

    def form_valid(self, form: LocalResetConfirmForm) -> HttpResponse:
        response = super().form_valid(form)
        record_event("identity.password.reset_link_used", actor=form.user, subject=form.user)
        return response


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "identity/profile.html")


@login_required
@require_http_methods(["GET", "POST"])
def logout_confirm(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        user = authenticated_user(request)
        record_event("identity.logout", actor=user, subject=user)
        logout(request)
        return redirect("identity:login")
    accessed_messages = request.session.get("accessed_messages", [])
    return render(
        request,
        "identity/logout_confirm.html",
        {"accessed_messages": accessed_messages},
    )


@login_required
def user_list(request: HttpRequest) -> HttpResponse:
    actor = authenticated_user(request)
    if not has_capability(actor, MANAGE_USERS):
        raise PermissionDenied
    users = visible_users_for(actor)
    query = request.GET.get("q", "").strip()
    if len(query) >= 3:
        from django.db.models import Q

        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    elif query:
        users = users.none()
        messages.info(request, "Enter at least three characters to search.")
    return render(request, "identity/user_list.html", {"users": users[:100], "query": query})


@login_required
@require_http_methods(["GET", "POST"])
def user_create(request: HttpRequest) -> HttpResponse:
    actor = authenticated_user(request)
    if not has_capability(actor, MANAGE_USERS):
        raise PermissionDenied
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        user, password = provision_local_user(actor=actor, values=values)
        request.session["one_time_password"] = password
        request.session["one_time_password_user"] = user.username
        return redirect("identity:one-time-password")
    return render(request, "identity/user_form.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def user_reset_password(request: HttpRequest, user_id: int) -> HttpResponse:
    actor = authenticated_user(request)
    if not has_capability(actor, MANAGE_USERS):
        raise PermissionDenied
    user = get_object_or_404(visible_users_for(actor), pk=user_id)
    request.session["one_time_password"] = reset_local_password(actor=actor, user=user)
    request.session["one_time_password_user"] = user.username
    return redirect("identity:one-time-password")


@login_required
def one_time_password(request: HttpRequest) -> HttpResponse:
    actor = authenticated_user(request)
    if not has_capability(actor, MANAGE_USERS):
        raise PermissionDenied
    password = request.session.pop("one_time_password", None)
    username = request.session.pop("one_time_password_user", None)
    if not password:
        return redirect("identity:user-list")
    return render(
        request,
        "identity/one_time_password.html",
        {"temporary_password": password, "username": username},
    )


password_reset_done = PasswordResetDoneView.as_view(
    template_name="identity/password_reset_done.html"
)
password_reset_complete = PasswordResetCompleteView.as_view(
    template_name="identity/password_reset_complete.html"
)
