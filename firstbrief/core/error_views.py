"""Content-negotiated error responses with correlation IDs."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from firstbrief.core.middleware import get_correlation_id


def _error_response(
    request: HttpRequest,
    *,
    status: int,
    title: str,
    message: str,
) -> HttpResponse:
    context: dict[str, Any] = {
        "status": status,
        "title": title,
        "message": message,
        "correlation_id": get_correlation_id(),
    }
    if request.accepts("text/html"):
        return render(request, "error.html", context=context, status=status)
    return JsonResponse(context, status=status)


def bad_request(request: HttpRequest, exception: Exception) -> HttpResponse:
    return _error_response(
        request,
        status=400,
        title="Bad request",
        message="The request could not be processed.",
    )


def permission_denied(request: HttpRequest, exception: Exception) -> HttpResponse:
    return _error_response(
        request,
        status=403,
        title="Permission denied",
        message="You do not have permission to perform this action.",
    )


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    return _error_response(
        request,
        status=404,
        title="Page not found",
        message="The requested page could not be found.",
    )


def server_error(request: HttpRequest) -> HttpResponse:
    return _error_response(
        request,
        status=500,
        title="Service unavailable",
        message="An unexpected error occurred. Use the reference below when seeking help.",
    )
