"""Seed the example project with the demo user the endpoints resolve tokens to."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import Permission, User
from django.core.management.base import BaseCommand, CommandParser

DEMO_USERNAME = "mcp-test-user"
DELETE_PERM_CODENAME = "delete_user"


class Command(BaseCommand):
    """Create ``mcp-test-user`` and optionally toggle its widget-delete permission.

    The bearer endpoints resolve the demo token to this user, so seeding is
    what makes ``current_username``, ``delete_widget`` and the filtered
    tools/list demonstrable on a live server. ``--grant-delete`` /
    ``--revoke-delete`` flip the permission the locked tool gates on.
    """

    help = "Create the demo user; --grant-delete/--revoke-delete toggle its permission."

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--grant-delete", action="store_true", help="Grant auth.delete_user to the demo user.")
        group.add_argument("--revoke-delete", action="store_true", help="Revoke auth.delete_user from the demo user.")

    def handle(self, *args: Any, **options: Any) -> None:
        user, created = User.objects.get_or_create(username=DEMO_USERNAME)
        self.stdout.write(f"{DEMO_USERNAME}: {'created' if created else 'already present'}")

        permission = Permission.objects.get(codename=DELETE_PERM_CODENAME)
        if options["grant_delete"]:
            user.user_permissions.add(permission)
            self.stdout.write(f"granted auth.{DELETE_PERM_CODENAME}")
        if options["revoke_delete"]:
            user.user_permissions.remove(permission)
            self.stdout.write(f"revoked auth.{DELETE_PERM_CODENAME}")
