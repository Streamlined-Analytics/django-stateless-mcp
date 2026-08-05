"""Admin registrations for the Book/Author demo.

The admin exists so a reader can toggle *Can update authors* on the demo
user through a GUI and watch the MCP tool list change in Inspector.
"""

from __future__ import annotations

from django.contrib import admin

from example.models import Author, Book


class BookInline(admin.TabularInline[Book, Author]):
    """Edit an author's books on the author page."""

    model = Book
    extra = 0


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin[Author]):
    """Authors with their books inline."""

    list_display = ["name"]
    inlines = [BookInline]


@admin.register(Book)
class BookAdmin(admin.ModelAdmin[Book]):
    """Books listed with their author."""

    list_display = ["title", "author"]
    list_select_related = ["author"]
