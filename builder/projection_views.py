"""Canonical orthographic views, in Blender Z-up coordinates."""

import math

PROJECTION_VIEWS = {
    "front": (math.pi / 2, 0.0, 0.0),
    "back": (math.pi / 2, 0.0, math.pi),
    "right": (math.pi / 2, 0.0, math.pi / 2),
    "left": (math.pi / 2, 0.0, -math.pi / 2),
    "top": (0.0, 0.0, 0.0),
    "bottom": (math.pi, 0.0, 0.0),
}
PREVIEW_NAMES = ("iso", *PROJECTION_VIEWS)
PREVIEW_FILES = tuple(f"preview_{name}.png" for name in PREVIEW_NAMES)


def projection_scale(lo, hi):
    """Identical pixels/metre on every square orthographic projection."""
    return max(max(float(hi[i]) - float(lo[i]) for i in range(3)) * 1.18, 0.5)
