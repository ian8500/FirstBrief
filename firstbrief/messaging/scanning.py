"""Fail-closed malware scanning interface and ClamAV adapter."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    detail: str


class MalwareScanner(Protocol):
    def scan(self, path: Path) -> ScanResult: ...


class UnavailableScanner:
    """Safe default: uploads cannot leave quarantine without a scanner."""

    def scan(self, path: Path) -> ScanResult:
        return ScanResult(False, "Malware scanner is not configured.")


class ClamAvScanner:
    """Invoke clamdscan without shell interpolation."""

    def scan(self, path: Path) -> ScanResult:
        executable = getattr(settings, "FIRSTBRIEF_CLAMD_SCAN_BIN", "/usr/bin/clamdscan")
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv; shell execution is disabled.
                [executable, "--fdpass", "--no-summary", str(path)],
                capture_output=True,
                check=False,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ScanResult(False, f"Scanner unavailable: {exc.__class__.__name__}")
        detail = (result.stdout or result.stderr).strip()[:255]
        return ScanResult(result.returncode == 0, detail or "ClamAV scan completed.")


def get_scanner() -> MalwareScanner:
    scanner_path = getattr(
        settings,
        "FIRSTBRIEF_MALWARE_SCANNER",
        "firstbrief.messaging.scanning.UnavailableScanner",
    )
    scanner_class = import_string(scanner_path)
    return cast(MalwareScanner, scanner_class())
