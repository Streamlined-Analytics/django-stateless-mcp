"""The example project's Book/Author domain, in the style of Django's own docs.

Two deliberately small models give the MCP tools something real to read and
write, and carry the custom permission the permission demos gate on.
"""

from __future__ import annotations

from django.db import models


class Author(models.Model):
    """A book author; carries the custom permission the demo tools gate on."""

    name = models.CharField(max_length=200)

    class Meta:
        permissions = [("can_update_authors", "Can update authors")]

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    """A book by a single author."""

    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    def __str__(self) -> str:
        return self.title
