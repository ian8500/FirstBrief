"""Protected PDF navigation metadata derived after message authorisation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.files.storage import default_storage
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from firstbrief.messaging.models import FileAsset


@dataclass(frozen=True)
class PdfPagePreview:
    page: int
    label: str
    excerpt: str
    text: str


@dataclass(frozen=True)
class PdfBookmark:
    title: str
    page: int
    level: int


@dataclass(frozen=True)
class PdfNavigation:
    pages: tuple[PdfPagePreview, ...]
    bookmarks: tuple[PdfBookmark, ...]
    available: bool
    message: str

    @property
    def total_pages(self) -> int:
        return len(self.pages)


def _flatten_outline(
    reader: PdfReader,
    values: list[Any],
    *,
    level: int = 0,
) -> list[PdfBookmark]:
    result: list[PdfBookmark] = []
    for value in values:
        if isinstance(value, list):
            result.extend(_flatten_outline(reader, value, level=level + 1))
            continue
        try:
            page_index = reader.get_destination_page_number(value)
            if page_index is None:
                continue
            page = page_index + 1
            title = str(value.title).strip()
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if title and page > 0:
            result.append(PdfBookmark(title=title, page=page, level=level))
    return result


def pdf_navigation(asset: FileAsset) -> PdfNavigation:
    try:
        with default_storage.open(asset.storage_key, "rb") as handle:
            reader = PdfReader(handle, strict=True)
            pages: list[PdfPagePreview] = []
            for index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                normalised = " ".join(text.split())
                pages.append(
                    PdfPagePreview(
                        page=index,
                        label=f"Page {index}",
                        excerpt=normalised[:180] or "No searchable text on this page.",
                        text=normalised[:20_000],
                    )
                )
            try:
                outline = list(reader.outline)
            except (AttributeError, KeyError, TypeError, ValueError):
                outline = []
            bookmarks = _flatten_outline(reader, outline)
    except (OSError, PdfReadError, ValueError):
        return PdfNavigation(
            pages=(),
            bookmarks=(),
            available=False,
            message="Page previews and text search are unavailable for this PDF.",
        )
    return PdfNavigation(
        pages=tuple(pages),
        bookmarks=tuple(bookmarks),
        available=True,
        message=(
            "Search uses text embedded in the protected PDF."
            if any(page.text for page in pages)
            else "This PDF does not contain searchable text."
        ),
    )
