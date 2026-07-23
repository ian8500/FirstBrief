#!/usr/bin/env python3
"""Django's command-line utility for administrative tasks."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "firstbrief.settings.development",
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django is not installed. Install requirements/dev.txt first.") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
