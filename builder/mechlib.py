"""Power-transmission helpers for mechanism generators (runs inside Blender, next to voxlib).

Wheels lie in the local XY plane and turn about +Z. Belt and chain loops are closed polylines
in that plane; markers run along them in the shared `work` loop. Changing this module changes
the output of every generator that imports it: bump their `generator_version`.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from mathutils import Vector

import voxlib as vx

Point = tuple[float, float]


# ---------------------------------------------------------------------- geometry

def outward(face: list[tuple[float, float, float]], centre: Vector) -> list[tuple[float, float, float]]:
    """Wind a face so its normal points away from `centre` (convex or star-shaped solids)."""
    a, b, c = (Vector(p) for p in face[:3])
    mid = sum((Vector(p) for p in face), Vector()) / len(face)
    return face if (b - a).cross(c - a).dot(mid - centre) >= 0 else list(reversed(face))


def convex_prism(m: vx.MeshBuilder, outline: list[Point], z0: float, z1: float, color: str) -> None:
    """Extrude a convex XY outline along Z."""
    n = len(outline)
    faces = [[(x, y, z0) for x, y in outline], [(x, y, z1) for x, y in outline]]
    faces += [[(*outline[i], z0), (*outline[(i + 1) % n], z0), (*outline[(i + 1) % n], z1), (*outline[i], z1)]
              for i in range(n)]
    centre = Vector((sum(x for x, _ in outline) / n, sum(y for _, y in outline) / n, (z0 + z1) / 2))
    for face in faces:
        m.polygon(outward(face, centre), color)


def wheel(m: vx.MeshBuilder, kind: str, r: float, width: float, color: str, accent: str, *,
          spokes: int = 5, teeth: int = 18, holes: bool = True) -> int:
    """A pulley or sprocket around the origin, z from 0 to `width`. Returns its symmetry order.

    A sprocket without `holes` is symmetric to one tooth, so a chain can drive it exactly."""
    hub = max(0.04, r * 0.2)
    sides = 16
    if kind == "flat":                                         # crowned rim and spokes
        m.ring(r * 0.86, r, 0.0, width, color, sides=sides)
        m.ring(r * 0.95, r * 1.01, width * 0.35, width * 0.65, color, sides=sides)    # crown
        for s in range(spokes):
            a = 2 * math.pi * s / spokes
            m.strut((hub * math.cos(a), hub * math.sin(a), width / 2),
                    (r * 0.88 * math.cos(a), r * 0.88 * math.sin(a), width / 2), max(0.02, r * 0.09), color,
                    depth=width * 0.45)
        sym = spokes
    elif kind == "vgroove":                                    # three lands, the grooves between them
        m.ring(r * 0.6, r * 0.86, 0.0, width, color, sides=sides)
        for i in range(3):
            z0 = width * (2 * i) / 5
            m.ring(r * 0.86, r, z0, z0 + width / 5, color, sides=sides)
        m.prism(r * 0.62, width * 0.3, width * 0.7, color, sides=sides)
        sym = 3
    elif kind == "cone":                                       # three steps for speed changes
        for i, f in enumerate((1.0, 0.78, 0.56)):
            m.prism(r * f, width * i / 3, width * (i + 1) / 3, color, sides=sides)
        sym = 3
    else:                                                      # sprocket
        depth = min(0.05, r * 0.18)
        root = r - depth
        for i in range(teeth):
            a, half = 2 * math.pi * i / teeth, math.pi / teeth
            convex_prism(m, [((root - 0.005) * math.cos(a - half * 0.7), (root - 0.005) * math.sin(a - half * 0.7)),
                             (r * math.cos(a - half * 0.25), r * math.sin(a - half * 0.25)),
                             (r * math.cos(a + half * 0.25), r * math.sin(a + half * 0.25)),
                             ((root - 0.005) * math.cos(a + half * 0.7), (root - 0.005) * math.sin(a + half * 0.7))],
                         width * 0.2, width * 0.8, color)
        m.prism(root, width * 0.2, width * 0.8, color, sides=teeth)
        for q in range(4 if holes else 0):
            a = math.pi / 4 + q * math.pi / 2
            m.prism(root * 0.16, width * 0.2 - 0.004, width * 0.8 + 0.004, "soot", sides=8,
                    center=(root * 0.55 * math.cos(a), root * 0.55 * math.sin(a)))
        sym = math.gcd(teeth, 4) if holes else teeth
    m.prism(hub, -0.01, width + 0.01, accent, sides=10)
    for s in range(3 if kind in ("vgroove", "cone") else 0):   # marks make solid wheels read as turning
        a = 2 * math.pi * s / 3
        x, y = hub * 0.6 * math.cos(a), hub * 0.6 * math.sin(a)
        m.box((x - 0.015, y - 0.015, width + 0.01), (x + 0.015, y + 0.015, width + 0.03), "brass")
    return sym


def spin(obj: "bpy.types.Object", turns: float, symmetry: int, name: str) -> float:  # noqa: F821
    """Spin about local Z by `turns`, rounded to the wheel's symmetry so the loop is seamless."""
    step = 1 / max(1, symmetry)
    rounded = round(turns / step) * step
    if rounded:
        vx.spin_animation(obj, name=name, axis=2, turns=rounded)
    return rounded


# ---------------------------------------------------------------------- belt paths

def _arc(c: Point, r: float, a0: float, a1: float, steps: int) -> list[Point]:
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / steps), c[1] + r * math.sin(a0 + (a1 - a0) * i / steps))
            for i in range(steps)]


def belt_loop(ra: float, rb: float, distance: float, angle: float, crossed: bool = False,
              steps: int = 8) -> tuple[list[Point], list[float]]:
    """Closed loop around wheel A (origin) and wheel B (distance along `angle`, radians), in the
    direction wheel A turns counter-clockwise. Returns points and a depth factor per point
    (−1…1 along the axles, 0 on the rims): the runs of a crossed belt leave both rims in the wheel
    plane and pass each other only where they cross."""
    b = (distance * math.cos(angle), distance * math.sin(angle))
    ratio = (ra + rb if crossed else ra - rb) / distance
    phi = math.asin(max(-0.95, min(0.95, ratio)))
    up, down = angle + math.pi / 2 - phi, angle - math.pi / 2 + phi       # tangent normals on A
    points: list[Point] = []
    depth: list[float] = []
    arc_a = _arc((0.0, 0.0), ra, up, down + 2 * math.pi, steps)           # back of A, counter-clockwise
    points += arc_a
    depth += [0.0] * len(arc_a)
    if crossed:
        # Internal tangents touch B opposite to A's normals; B is wrapped clockwise over its
        # front, from down + π to up - π (a sweep of π + 2φ), and turns the other way. Both runs
        # pass through the inner centre of similitude, which splits A–B in the ratio ra : rb.
        cross = (b[0] * ra / (ra + rb), b[1] * ra / (ra + rb))
        points += [(ra * math.cos(down), ra * math.sin(down)), cross]
        depth += [0.0, 1.0]
        arc_b = _arc(b, rb, down + math.pi, up - math.pi, steps)
        points += arc_b
        depth += [0.0] * len(arc_b)
        points += [(b[0] + rb * math.cos(up - math.pi), b[1] + rb * math.sin(up - math.pi)), cross]
        depth += [0.0, -1.0]
    else:
        points.append((ra * math.cos(down), ra * math.sin(down)))
        depth.append(0.0)
        arc_b = _arc(b, rb, down, up, steps)                              # front of B, counter-clockwise
        points += arc_b
        depth += [0.0] * len(arc_b)
        points.append((b[0] + rb * math.cos(up), b[1] + rb * math.sin(up)))
        depth.append(0.0)
    return points, depth


def loop_length(points: list[Point]) -> float:
    return sum(math.dist(points[i], points[(i + 1) % len(points)]) for i in range(len(points)))


def point_at(points: list[Point], s: float) -> tuple[float, float, float, int, float]:
    """(x, y, heading, segment index, fraction along it) at arc length s along the closed polyline."""
    n = len(points)
    for i in range(n):
        p, q = points[i], points[(i + 1) % n]
        seg = math.dist(p, q)
        if s <= seg or i == n - 1:
            f = min(1.0, s / seg) if seg else 0.0
            return p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f, math.atan2(q[1] - p[1], q[0] - p[0]), i, f
        s -= seg
    return points[0][0], points[0][1], 0.0, 0, 0.0


def depth_at(points: list[Point], depth: list[float], s: float) -> float:
    """Depth factor at arc length s: linear between the points' factors."""
    *_, i, f = point_at(points, s)
    return depth[i] + (depth[(i + 1) % len(depth)] - depth[i]) * f


def draw_loop(m: vx.MeshBuilder, points: list[Point], z: float, width: float, thickness: float, color: str,
              depth: list[float] | None = None, cross_offset: float = 0.0) -> None:
    """Static belt: a strut per polyline segment, `width` along Z, `thickness` in the plane; each
    point is lifted by its depth factor × `cross_offset` along Z."""
    n = len(points)
    for i in range(n):
        p, q = points[i], points[(i + 1) % n]
        dp = depth[i] * cross_offset if depth else 0.0
        dq = depth[(i + 1) % n] * cross_offset if depth else 0.0
        m.strut((p[0], p[1], z + dp), (q[0], q[1], z + dq), thickness, color, depth=width)


def run_markers(parent: "bpy.types.Object", name: str, points: list[Point], z: float,  # noqa: F821
                speed: float, make: Callable[[vx.MeshBuilder], None], *, spacing: float = 0.3,
                semantic: str = "belt", depth: list[float] | None = None, cross_offset: float = 0.0) -> int:
    """Identical markers every ~`spacing` along the loop, moving `speed` metres per loop.

    The speed is rounded to whole marker spacings, so the set of markers looks the same at the
    end of the loop as at the start. Markers vanish for an instant where the path closes."""
    length = loop_length(points)
    count = max(4, round(length / spacing))
    step = length / count
    travel = round(speed / step) * step
    for i in range(count):
        mb = vx.MeshBuilder()
        make(mb)
        marker = mb.to_object(f"{name}_{i:02d}", parent=parent, location=(0.0, 0.0, z), semantic_part=semantic)

        def s_at(t: float, i: int = i) -> float:
            return (i * step + travel * t) % length

        for axis in (0, 1):
            vx.periodic_animation(marker, "location", axis, lambda t, a=axis, f=s_at: point_at(points, f(t))[a],
                                  step=1, name=f"{name}_{i:02d}")
        vx.periodic_animation(marker, "rotation_euler", 2, lambda t, f=s_at: point_at(points, f(t))[2], step=1)
        if depth and cross_offset:                             # follow the crossed runs in depth
            vx.periodic_animation(marker, "location", 2,
                                  lambda t, f=s_at: z + depth_at(points, depth, f(t)) * cross_offset, step=1)
        for axis in range(3):
            vx.periodic_animation(marker, "scale", axis,
                                  lambda t, f=s_at: 1e-3 if min(f(t), length - f(t)) < step * 0.15 else 1.0, step=1)
    return count
