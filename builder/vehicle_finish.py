"""Small, Blender-independent role lookup for recipe-local vehicle finishes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def color(params: Mapping[str, Any], role: str, fallback: str) -> str:
    """Return the selected role's palette color, or the generator's legacy fallback."""
    finish = params.get("_finish")
    if isinstance(finish, Mapping):
        colors = finish.get("colors")
        if isinstance(colors, Mapping):
            value = colors.get(role)
            if isinstance(value, str) and value:
                return value
    return fallback
