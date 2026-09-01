from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any


STATES = ("todo", "in_progress", "done")
SIZES = ("S", "M", "L")
PRIORITIES = (1, 2, 3, 4, 5)
ID_PATTERN = re.compile(r"^T\d{4,}$")


class BacklogError(Exception):
    """A user-facing backlog error."""


class ValidationError(BacklogError):
    """A task or backlog is invalid."""


class NotFoundError(BacklogError):
    """A requested backlog or task does not exist."""


class ConflictError(BacklogError):
    """A task changed after it was read."""


def normalize_tags(value: list[str] | None) -> list[str]:
    """Validate and normalize the optional, ordered task tag list."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("tags must be a JSON array of non-empty strings")
    tags: list[str] = []
    seen: set[str] = set()
    for tag in value:
        if not isinstance(tag, str):
            raise ValidationError("tags must be a JSON array of non-empty strings")
        normalized = tag.strip()
        if not normalized or "\n" in normalized or "\r" in normalized:
            raise ValidationError("each tag must be a non-empty single line")
        key = normalized.casefold()
        if key in seen:
            raise ValidationError("tags must not contain duplicates")
        seen.add(key)
        tags.append(normalized)
    return tags


def parse_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO 8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO 8601 timestamp") from exc


@dataclass(slots=True)
class Task:
    id: str
    title: str
    release: str | None
    priority: int
    size: str | None
    state: str
    created: str
    done: str | None
    tags: list[str] = field(default_factory=list)
    body: str = ""

    def validate(self) -> None:
        errors: list[str] = []
        if not ID_PATTERN.fullmatch(self.id):
            errors.append("id must look like T0001")
        if not isinstance(self.title, str) or not self.title.strip():
            errors.append("title must not be empty")
        elif "\n" in self.title or "\r" in self.title:
            errors.append("title must be a single line")
        if self.release is not None and (
            not isinstance(self.release, str) or not self.release.strip()
        ):
            errors.append("release must be null, next, or a non-empty version string")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            errors.append("priority must be an integer")
        elif self.priority not in PRIORITIES:
            errors.append("priority must be one of 1, 2, 3, 4, or 5")
        if self.size is not None and self.size not in SIZES:
            errors.append(f"size must be one of {', '.join(SIZES)}, or null")
        if self.state not in STATES:
            errors.append(f"state must be one of {', '.join(STATES)}")
        try:
            parse_timestamp(self.created, "created")
        except ValidationError as exc:
            errors.append(str(exc))
        if self.done is not None:
            try:
                parse_timestamp(self.done, "done")
            except ValidationError as exc:
                errors.append(str(exc))
        if self.state == "done" and self.done is None:
            errors.append("done must contain a timestamp when state is done")
        if self.state != "done" and self.done is not None:
            errors.append("done must be null unless state is done")
        try:
            normalized_tags = normalize_tags(self.tags)
            if normalized_tags != self.tags:
                errors.append("tags must not have leading or trailing whitespace")
        except ValidationError as exc:
            errors.append(str(exc))
        if not isinstance(self.body, str):
            errors.append("Markdown body must be text")
        if errors:
            raise ValidationError("; ".join(errors))

    def as_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "release": self.release,
            "priority": self.priority,
            "size": self.size,
            "state": self.state,
            "created": self.created,
            "done": self.done,
        }
        if self.tags:
            result["tags"] = self.tags
        if include_body:
            result["body"] = self.body
        return result
