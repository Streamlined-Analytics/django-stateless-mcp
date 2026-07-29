#!/usr/bin/env python
"""Django management entrypoint for the example project."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Run a management command against the example project."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
