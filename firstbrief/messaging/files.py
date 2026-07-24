"""Quarantined PDF validation, scanning and opaque protected storage."""

from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from firstbrief.identity.models import User
from firstbrief.messaging.models import FileAsset, MessagePolicy, MessageVersion
from firstbrief.messaging.scanning import MalwareScanner


def _extract_searchable_text(payload: bytes) -> str:
    """Extract bounded display text without exposing or persisting the PDF itself."""
    reader = PdfReader(io.BytesIO(payload), strict=True)
    parts: list[str] = []
    remaining = 200_000
    for page in reader.pages:
        if remaining <= 0:
            break
        text = (page.extract_text() or "").strip()
        if text:
            excerpt = text[:remaining]
            parts.append(excerpt)
            remaining -= len(excerpt)
    return "\n".join(parts)


def _read_validated_pdf(upload: UploadedFile, message_id: str) -> bytes:
    policy = MessagePolicy.load()
    upload_size = upload.size
    if upload_size is None:
        raise ValidationError("The PDF size could not be determined.")
    if upload_size > policy.maximum_pdf_bytes:
        raise ValidationError(f"PDF exceeds the {policy.maximum_pdf_bytes}-byte limit.")
    if upload.content_type not in {"application/pdf", "application/x-pdf"}:
        raise ValidationError("Only PDF uploads are accepted.")
    upload_name = upload.name or ""
    expected_name = f"{message_id}.pdf".casefold()
    if policy.enforce_pdf_filename_match and Path(upload_name).name.casefold() != expected_name:
        raise ValidationError(f"PDF filename must be {message_id}.pdf.")
    payload = b"".join(upload.chunks())
    if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-2048:]:
        raise ValidationError("The upload is not a structurally valid PDF.")
    try:
        reader = PdfReader(io.BytesIO(payload), strict=True)
        if not reader.pages:
            raise ValidationError("The PDF must contain at least one page.")
    except (PdfReadError, ValueError, OSError) as exc:
        raise ValidationError("The upload is not a structurally valid PDF.") from exc
    return payload


def store_scanned_pdf(
    *,
    version: MessageVersion,
    role: str,
    upload: UploadedFile,
    actor: User,
    scanner: MalwareScanner,
) -> FileAsset:
    payload = _read_validated_pdf(upload, version.message.message_id)
    upload_name = upload.name or ""
    key = f"quarantine/{uuid.uuid4().hex}.pdf"
    saved_key = default_storage.save(key, ContentFile(payload))
    try:
        path = Path(default_storage.path(saved_key))
        scan = scanner.scan(path)
        if not scan.clean:
            raise ValidationError(f"PDF was not accepted: {scan.detail}")
        searchable_text = (
            _extract_searchable_text(payload) if role == FileAsset.Role.DISPLAY else ""
        )
        asset = FileAsset.objects.create(
            version=version,
            role=role,
            original_filename=Path(upload_name).name,
            storage_key=saved_key,
            content_type="application/pdf",
            byte_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            scan_status=FileAsset.ScanStatus.CLEAN,
            scan_detail=scan.detail,
            uploaded_by=actor,
        )
        if role == FileAsset.Role.DISPLAY:
            version.searchable_content = searchable_text
            version.save(update_fields=("searchable_content",))
        return asset
    except Exception:
        default_storage.delete(saved_key)
        raise


def attach_message_pdfs(
    *,
    version: MessageVersion,
    display_upload: UploadedFile,
    print_upload: UploadedFile,
    actor: User,
    scanner: MalwareScanner,
) -> list[FileAsset]:
    assets: list[FileAsset] = []
    try:
        for role, upload in (
            (FileAsset.Role.DISPLAY, display_upload),
            (FileAsset.Role.PRINT, print_upload),
        ):
            assets.append(
                store_scanned_pdf(
                    version=version,
                    role=role,
                    upload=upload,
                    actor=actor,
                    scanner=scanner,
                )
            )
        return assets
    except Exception:
        for asset in assets:
            default_storage.delete(asset.storage_key)
            asset.delete()
        raise
