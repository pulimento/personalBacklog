"""Small TOON 3.3 encoder for the JSON-shaped values emitted by the CLI.

This intentionally implements the shapes Personal Backlog outputs: primitive
objects, uniform arrays of primitive objects, primitive arrays, and nested task
metadata such as tags. It is an output adapter, not a general TOON library.
"""

from __future__ import annotations

from decimal import Decimal
import math
import re
from typing import Any


_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_NUMBER_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$", re.IGNORECASE)


def dumps(value: object) -> str:
    """Encode a Personal Backlog CLI value as TOON 3.3 text."""
    if _is_primitive(value):
        return _primitive(value)
    if isinstance(value, dict):
        return "\n".join(_object_lines(value, 0))
    if isinstance(value, list):
        return "\n".join(_array_lines(value, 0, None))
    raise TypeError(f"unsupported TOON value: {type(value).__name__}")


def _is_primitive(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _primitive(value: object, delimiter: str = ",") -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _string(value, delimiter)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _number(value)
    raise TypeError(f"unsupported TOON primitive: {type(value).__name__}")


def _number(value: float) -> str:
    if not math.isfinite(value):
        return "null"
    if value == 0:
        return "0"
    absolute = abs(value)
    if 1e-6 <= absolute < 1e21:
        if value.is_integer():
            return str(int(value))
        return format(Decimal(repr(value)), "f")
    rendered = repr(value).lower()
    return re.sub(r"e([+-])0+(\d+)$", r"e\1\2", rendered)


def _string(value: str, delimiter: str) -> str:
    must_quote = (
        not value
        or value != value.strip()
        or value in {"true", "false", "null"}
        or _NUMBER_PATTERN.fullmatch(value) is not None
        or any(character in value for character in ':"\\[]{}')
        or any(ord(character) < 0x20 for character in value)
        or delimiter in value
        or value.startswith("-")
    )
    return _quoted(value) if must_quote else value


def _quoted(value: str) -> str:
    characters: list[str] = ['"']
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for character in value:
        codepoint = ord(character)
        if character in escapes:
            characters.append(escapes[character])
        elif codepoint < 0x20:
            characters.append(f"\\u{codepoint:04x}")
        elif 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("TOON strings cannot contain lone Unicode surrogates")
        else:
            characters.append(character)
    characters.append('"')
    return "".join(characters)


def _key(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("TOON object keys must be strings")
    return value if _KEY_PATTERN.fullmatch(value) else _quoted(value)


def _object_lines(value: dict[Any, Any], depth: int) -> list[str]:
    lines: list[str] = []
    indentation = "  " * depth
    for raw_key, item in value.items():
        key = _key(raw_key)
        if _is_primitive(item):
            lines.append(f"{indentation}{key}: {_primitive(item)}")
        elif isinstance(item, dict):
            lines.append(f"{indentation}{key}:")
            lines.extend(_object_lines(item, depth + 1))
        elif isinstance(item, list):
            lines.extend(_array_lines(item, depth, key))
        else:
            raise TypeError(f"unsupported TOON value: {type(item).__name__}")
    return lines


def _array_lines(value: list[Any], depth: int, key: str | None) -> list[str]:
    indentation = "  " * depth
    prefix = f"{indentation}{key}" if key is not None else indentation
    if not value:
        return [f"{prefix}: []" if key is not None else "[]"]
    if all(_is_primitive(item) for item in value):
        cells = ",".join(_primitive(item) for item in value)
        return [f"{prefix}[{len(value)}]: {cells}"]
    if _is_tabular(value):
        fields = list(value[0])
        field_names = ",".join(_key(field) for field in fields)
        lines = [f"{prefix}[{len(value)}]{{{field_names}}}:"]
        for item in value:
            cells = ",".join(_primitive(item[field]) for field in fields)
            lines.append(f"{'  ' * (depth + 1)}{cells}")
        return lines
    if all(isinstance(item, dict) for item in value):
        lines = [f"{prefix}[{len(value)}]:"]
        for item in value:
            lines.append(f"{'  ' * (depth + 1)}-")
            lines.extend(_object_lines(item, depth + 2))
        return lines
    raise TypeError("TOON output does not support this non-uniform array shape")


def _is_tabular(value: list[Any]) -> bool:
    if not value or not all(isinstance(item, dict) and item for item in value):
        return False
    fields = set(value[0])
    return all(
        set(item) == fields and all(_is_primitive(cell) for cell in item.values())
        for item in value
    )
