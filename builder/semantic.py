"""Small, Blender-independent placement rules for procedural RTS geometry.

All coordinates are Blender metres (Z up). These functions make repeated
placement and relationships exact; they do not implicitly snap artistic shapes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

Point3 = tuple[float, float, float]

MACRO_GRID = 0.25      # structure: primary masses, bounds, anchors, pivots, sockets, joints
DETAIL_GRID = 0.0625   # details: frames, panels, small offsets, secondary members


def _point(value: Sequence[float]) -> Point3:
    if len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
        raise ValueError("expected three finite coordinates")
    return (float(value[0]), float(value[1]), float(value[2]))


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class Bounds:
    """A box whose anchors are derived from its extents, never magic offsets."""

    minimum: Point3
    maximum: Point3

    def __post_init__(self) -> None:
        mn, mx = _point(self.minimum), _point(self.maximum)
        if any(a >= b for a, b in zip(mn, mx)):
            raise ValueError("bounds maximum must exceed minimum on every axis")
        object.__setattr__(self, "minimum", mn)
        object.__setattr__(self, "maximum", mx)

    @classmethod
    def from_center_size(cls, center: Sequence[float], size: Sequence[float]) -> Bounds:
        c, s = _point(center), _point(size)
        if any(v <= 0 for v in s):
            raise ValueError("size must be positive on every axis")
        return cls(tuple(c[i] - s[i] / 2 for i in range(3)),
                   tuple(c[i] + s[i] / 2 for i in range(3)))

    @property
    def center(self) -> Point3:
        return tuple((a + b) / 2 for a, b in zip(self.minimum, self.maximum))  # type: ignore[return-value]

    @property
    def size(self) -> Point3:
        return tuple(b - a for a, b in zip(self.minimum, self.maximum))  # type: ignore[return-value]

    @property
    def left(self) -> float:
        return self.minimum[0]

    @property
    def right(self) -> float:
        return self.maximum[0]

    @property
    def front(self) -> float:
        return self.minimum[1]

    @property
    def back(self) -> float:
        return self.maximum[1]

    @property
    def bottom(self) -> float:
        return self.minimum[2]

    @property
    def top(self) -> float:
        return self.maximum[2]

    def anchor(self, *, x: str = "center", y: str = "center", z: str = "center") -> Point3:
        """Pick a named point on the box, e.g. x='left', y='front', z='top'."""
        aliases = (
            {"left": 0, "min": 0, "center": 1, "right": 2, "max": 2},
            {"front": 0, "min": 0, "center": 1, "back": 2, "max": 2},
            {"bottom": 0, "min": 0, "center": 1, "top": 2, "max": 2},
        )
        selectors = (x, y, z)
        result = []
        for axis, key in enumerate(selectors):
            try:
                choice = aliases[axis][key]
            except KeyError as exc:
                raise ValueError(f"unknown {('x', 'y', 'z')[axis]} anchor: {key}") from exc
            result.append((self.minimum[axis], self.center[axis], self.maximum[axis])[choice])
        return (result[0], result[1], result[2])

    def edge(self, side: str, *, z: str = "top", inset: float = 0.0) -> tuple[Point3, Point3]:
        """Horizontal front/back/left/right edge, optionally moved toward the centre."""
        inset = _finite(inset, "inset")
        if inset < 0:
            raise ValueError("inset must not be negative")
        elevation = self.anchor(z=z)[2]
        if side in ("front", "back"):
            if inset > self.size[1] / 2:
                raise ValueError("inset exceeds half the box depth")
            y = self.front + inset if side == "front" else self.back - inset
            return ((self.left, y, elevation), (self.right, y, elevation))
        if side in ("left", "right"):
            if inset > self.size[0] / 2:
                raise ValueError("inset exceeds half the box width")
            x = self.left + inset if side == "left" else self.right - inset
            return ((x, self.front, elevation), (x, self.back, elevation))
        raise ValueError(f"unknown edge: {side}")


def evenly_spaced(start: float, end: float, count: int) -> tuple[float, ...]:
    """Include both endpoints; a single element sits at the midpoint."""
    start, end = _finite(start, "start"), _finite(end, "end")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    if count == 1:
        return ((start + end) / 2,)
    return (start, *(start + (end - start) * i / (count - 1) for i in range(1, count - 1)), end)


def centered_array(count: int, spacing: float, *, center: float = 0.0) -> tuple[float, ...]:
    """Positions of repeated parts centred around a nominal anchor."""
    spacing, center = _finite(spacing, "spacing"), _finite(center, "center")
    if spacing < 0:
        raise ValueError("spacing must not be negative")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    start = center - spacing * (count - 1) / 2
    return tuple(start + i * spacing for i in range(count))


def mirrored_pair(offset: float, *, center: float = 0.0) -> tuple[float, float]:
    """Symmetric offsets around a centre on one selected axis."""
    offset, center = _finite(offset, "offset"), _finite(center, "center")
    if offset < 0:
        raise ValueError("offset must not be negative")
    return (center - offset, center + offset)


def distribute_between(start: Sequence[float], end: Sequence[float], count: int) -> tuple[Point3, ...]:
    """Linearly spaced 3D anchors, including both endpoints."""
    a, b = _point(start), _point(end)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("count must be a positive integer")
    if count == 1:
        return (tuple((a[i] + b[i]) / 2 for i in range(3)),)  # type: ignore[return-value]
    result = [a]
    result.extend(tuple(a[j] + (b[j] - a[j]) * i / (count - 1) for j in range(3))
                  for i in range(1, count - 1))
    result.append(b)
    return tuple(result)


def quantize(value: float, *, grid: str | float = "structural", voxel_size: float = 0.25) -> float:
    """Explicit half-away-from-zero snap. Detail grid is one quarter of voxel size."""
    value, voxel_size = _finite(value, "value"), _finite(voxel_size, "voxel_size")
    if voxel_size <= 0:
        raise ValueError("voxel_size must be positive")
    if grid == "structural":
        step = voxel_size
    elif grid == "detail":
        step = voxel_size / 4
    elif isinstance(grid, (int, float)) and not isinstance(grid, bool):
        step = _finite(grid, "grid")
    else:
        raise ValueError("grid must be 'structural', 'detail', or a positive step")
    if step <= 0:
        raise ValueError("grid step must be positive")
    number = (Decimal(str(value)) / Decimal(str(step))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    snapped = float(number * Decimal(str(step)))
    return 0.0 if snapped == 0 else snapped


def snap_point(point: Sequence[float], *, grid: str | float = "structural",
               voxel_size: float = 0.25) -> Point3:
    p = _point(point)
    return tuple(quantize(v, grid=grid, voxel_size=voxel_size) for v in p)  # type: ignore[return-value]


def support_segment(top: Sequence[float], *, ground_z: float = 0.0) -> tuple[Point3, Point3]:
    """Vertical member endpoints; its lower face lies exactly on ground_z."""
    top = _point(top)
    ground_z = _finite(ground_z, "ground_z")
    if top[2] <= ground_z:
        raise ValueError("support top must be above ground")
    return ((top[0], top[1], ground_z), top)


def beam_corners(start: Sequence[float], end: Sequence[float], width: float,
                 *, depth: float | None = None) -> tuple[Point3, ...]:
    """Eight corners of a rectangular beam. End-face centres equal the anchors.

    Corners 0..3 belong to the start plane and 4..7 to the end plane.
    """
    a, b = _point(start), _point(end)
    width = _finite(width, "width")
    depth = width if depth is None else _finite(depth, "depth")
    if width <= 0 or depth <= 0:
        raise ValueError("beam width and depth must be positive")
    direction = tuple(b[i] - a[i] for i in range(3))
    length = math.sqrt(sum(v * v for v in direction))
    if length <= 1e-9:
        raise ValueError("beam anchors must differ")
    d = tuple(v / length for v in direction)
    reference = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (0.0, 1.0, 0.0)
    u = (reference[1] * d[2] - reference[2] * d[1],
         reference[2] * d[0] - reference[0] * d[2],
         reference[0] * d[1] - reference[1] * d[0])
    norm = math.sqrt(sum(v * v for v in u))
    u = tuple(v / norm for v in u)
    v = (d[1] * u[2] - d[2] * u[1],
         d[2] * u[0] - d[0] * u[2],
         d[0] * u[1] - d[1] * u[0])
    corners = []
    for origin in (a, b):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(tuple(origin[i] + sx * u[i] * width / 2 + sy * v[i] * depth / 2
                                 for i in range(3)))
    return tuple(corners)
