"""Authorised operational visibility and manual notification recovery."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_MESSAGES, has_capability
from firstbrief.notifications.forms import NotificationPolicyForm
from firstbrief.notifications.models import (
    LifecycleJob,
    NotificationJob,
    NotificationPolicy,
    OutboxEvent,
)
from firstbrief.notifications.services import manual_resend


def _manager(request: HttpRequest) -> User:
    user = request.user
    if not isinstance(user, User) or not has_capability(user, MANAGE_MESSAGES):
        raise PermissionDenied
    return user


@login_required
@require_http_methods(["GET", "POST"])
def operations(request: HttpRequest) -> HttpResponse:
    _manager(request)
    policy = NotificationPolicy.load()
    form = NotificationPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Notification policy updated.")
        return redirect("notifications:operations")
    return render(
        request,
        "notifications/operations.html",
        {
            "form": form,
            "outbox_dead": OutboxEvent.objects.filter(status=OutboxEvent.Status.DEAD),
            "lifecycle_dead": LifecycleJob.objects.filter(status=LifecycleJob.Status.DEAD),
            "notification_dead": NotificationJob.objects.filter(status=NotificationJob.Status.DEAD),
            "notification_recent": NotificationJob.objects.order_by("-created_at")[:25],
        },
    )


@login_required
@require_POST
def resend(request: HttpRequest, job_pk: int) -> HttpResponse:
    actor = _manager(request)
    job = get_object_or_404(NotificationJob, pk=job_pk)
    manual_resend(actor=actor, job=job)
    messages.success(request, "Notification queued for manual resend.")
    return redirect("notifications:operations")
