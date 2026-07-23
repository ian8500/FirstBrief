"""Permission-gated configuration tree/list administration."""

from dataclasses import dataclass
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from firstbrief.configuration.forms import (
    EmailDistributionForm,
    MessageGroupForm,
    MessageGroupTypeForm,
    MessageSubTypeForm,
    MessageTypeForm,
    PrimaryMessageGroupForm,
    SectorForm,
    SiteForm,
)
from firstbrief.configuration.models import (
    EmailDistribution,
    MessageGroup,
    MessageGroupType,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Sector,
    Site,
)
from firstbrief.configuration.services import delete_configuration, save_configuration
from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_CONFIGURATION, has_capability


@dataclass(frozen=True)
class RegistryEntry:
    label: str
    model: Any
    form: type


REGISTRY = {
    "sites": RegistryEntry("Sites", Site, SiteForm),
    "primary-groups": RegistryEntry(
        "Primary message groups", PrimaryMessageGroup, PrimaryMessageGroupForm
    ),
    "group-types": RegistryEntry("Message group types", MessageGroupType, MessageGroupTypeForm),
    "groups": RegistryEntry("Message groups", MessageGroup, MessageGroupForm),
    "message-types": RegistryEntry("Message types", MessageType, MessageTypeForm),
    "subtypes": RegistryEntry("Message subtypes", MessageSubType, MessageSubTypeForm),
    "sectors": RegistryEntry("Sectors", Sector, SectorForm),
    "distributions": RegistryEntry("Email distributions", EmailDistribution, EmailDistributionForm),
}


def actor_for(request: HttpRequest) -> User:
    if not isinstance(request.user, User) or not has_capability(request.user, MANAGE_CONFIGURATION):
        raise PermissionDenied
    return request.user


def entry_for(kind: str) -> RegistryEntry:
    try:
        return REGISTRY[kind]
    except KeyError as exc:
        raise Http404 from exc


@login_required
def index(request: HttpRequest) -> HttpResponse:
    actor_for(request)
    sections = [
        (kind, entry, entry.model.objects.all())
        for kind, entry in REGISTRY.items()
    ]
    return render(
        request,
        "configuration/index.html",
        {
            "sections": sections,
            "group_type_roots": MessageGroupType.objects.filter(parent=None).prefetch_related(
                "children"
            ),
            "group_roots": MessageGroup.objects.filter(parent=None).select_related("primary_group"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit(request: HttpRequest, kind: str, object_id: int | None = None) -> HttpResponse:
    actor = actor_for(request)
    entry = entry_for(kind)
    instance = get_object_or_404(entry.model, pk=object_id) if object_id else None
    form = entry.form(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        save_configuration(actor=actor, form=form)
        messages.success(request, f"{entry.label.rstrip('s')} saved.")
        return redirect("configuration:index")
    return render(
        request, "configuration/form.html",
        {"form": form, "entry": entry, "is_edit": bool(instance)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def delete(request: HttpRequest, kind: str, object_id: int) -> HttpResponse:
    actor = actor_for(request)
    entry = entry_for(kind)
    instance: Any = get_object_or_404(entry.model, pk=object_id)
    if request.method == "POST":
        try:
            delete_configuration(actor=actor, instance=instance)
        except ProtectedError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{entry.label.rstrip('s')} deleted successfully.")
        return redirect("configuration:index")
    return render(
        request, "configuration/confirm_delete.html",
        {"entry": entry, "object": instance},
    )
