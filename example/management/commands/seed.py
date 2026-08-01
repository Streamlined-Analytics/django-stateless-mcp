"""Seed the example project: demo user, admin superuser, and the book library."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import Permission, User
from django.core.management.base import BaseCommand, CommandParser

from example.models import Author, Book

DEMO_USERNAME = "mcp-test-user"
ADMIN_USERNAME = "admin"
# Demo-only credentials, published like the example's SECRET_KEY. See ADR-0033.
ADMIN_PASSWORD = "admin"
UPDATE_AUTHORS_CODENAME = "can_update_authors"

LIBRARY = {
    "Adrian Holovaty": ["The Definitive Guide to Django"],
    "Audrey Roy Greenfeld": ["Two Scoops of Django"],
    "Sally Author": ["Django for the Impatient", "Stateless by Design"],
}


class Command(BaseCommand):
    """Seed everything the live demo needs, idempotently.

    Creates ``mcp-test-user`` (the user the bearer endpoints resolve tokens
    to), the ``admin`` superuser for the permission-toggling walkthrough,
    and a small Book/Author library for the book tools to read.
    ``--grant-update-authors`` / ``--revoke-update-authors`` flip the custom
    permission the locked ``update_author`` tool gates on — the scriptable
    alternative to toggling it in the admin.
    """

    help = "Seed demo data; --grant-update-authors/--revoke-update-authors toggle the demo user's permission."

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--grant-update-authors",
            action="store_true",
            help="Grant example.can_update_authors to the demo user.",
        )
        group.add_argument(
            "--revoke-update-authors",
            action="store_true",
            help="Revoke example.can_update_authors from the demo user.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user, created = User.objects.get_or_create(username=DEMO_USERNAME)
        self.stdout.write(f"{DEMO_USERNAME}: {'created' if created else 'already present'}")

        self._seed_superuser()
        self._seed_library()

        permission = Permission.objects.get(codename=UPDATE_AUTHORS_CODENAME)
        if options["grant_update_authors"]:
            user.user_permissions.add(permission)
            self.stdout.write(f"granted example.{UPDATE_AUTHORS_CODENAME}")
        if options["revoke_update_authors"]:
            user.user_permissions.remove(permission)
            self.stdout.write(f"revoked example.{UPDATE_AUTHORS_CODENAME}")

    def _seed_superuser(self) -> None:
        """Create the demo-only ``admin``/``admin`` superuser once."""
        superuser, created = User.objects.get_or_create(
            username=ADMIN_USERNAME,
            defaults={"is_staff": True, "is_superuser": True},
        )
        if not created:
            self.stdout.write(f"{ADMIN_USERNAME}: already present")
            return
        superuser.set_password(ADMIN_PASSWORD)
        superuser.save()
        self.stdout.write(f"{ADMIN_USERNAME}: created (password '{ADMIN_PASSWORD}', demo only)")

    def _seed_library(self) -> None:
        """Create the Book/Author rows the book tools read."""
        book_count = 0
        for author_name, titles in LIBRARY.items():
            author, _ = Author.objects.get_or_create(name=author_name)
            for title in titles:
                _, created = Book.objects.get_or_create(title=title, author=author)
                book_count += int(created)
        self.stdout.write(f"library: {book_count} book(s) created")
