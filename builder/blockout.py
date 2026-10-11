"""Blockout contract: semantic masses → host faces → regions → ports, and stage roles.

Blender-independent, so tests check the structure of a model without building it.

- A model starts as a few large **masses** (BOX / WEDGE / lofted BEAM). Their bounds lie on
  MACRO_GRID; shaping corners (slopes, tapers) on DETAIL_GRID.
- Every mass has six planar named **faces** (front, back, left, right, top, bottom). Child
  geometry is derived from a face: a **region** is a metric rectangle in the face plane (a
  windscreen, a window, a door), materialised later as a PANEL or a FRAME.
- **Ports** are named structural anchors on MACRO_GRID (rotor mounts, tail mount, wheels).
  Parts dock through ports, never through look-alike numbers.
- Each primitive has a **role**; stage N shows roles up to N (mass 1 · form 2 · structure 3 ·
  detail 4 · accent 5). `until` retires a primitive once a later stage refines it, `group`
  names the stage-1 mass it refines (the refinement invariant is checked per group).

vehlib.render() draws a Plan in Blender."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterator, Sequence

try:
    from .semantic import DETAIL_GRID, MACRO_GRID, quantize
except ImportError:  # top-level import inside Blender (builder/ on sys.path)
    from semantic import DETAIL_GRID, MACRO_GRID, quantize

P3 = tuple[float, float, float]
ROLES = {"mass": 1, "form": 2, "structure": 3, "detail": 4, "accent": 5}
STAGES = {1: "MASSING", 2: "SILHOUETTE", 3: "STRUCTURE", 4: "DETAIL", 5: "GAME"}


# ---------------------------------------------------------------------------------- vectors
def add(a: Sequence[float], b: Sequence[float]) -> P3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Sequence[float], b: Sequence[float]) -> P3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Sequence[float], k: float) -> P3:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Sequence[float], b: Sequence[float]) -> P3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a: Sequence[float]) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Sequence[float]) -> P3:
    n = length(a)
    if n < 1e-12:
        raise ValueError("zero-length vector")
    return mul(a, 1.0 / n)


def lerp(a: Sequence[float], b: Sequence[float], t: float) -> P3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def mirror_x(p: Sequence[float]) -> P3:
    return (-p[0], p[1], p[2])


# ---------------------------------------------------------------------------------- grids
def on_grid(value: float, step: float = MACRO_GRID, tol: float = 1e-6) -> bool:
    return abs(value / step - round(value / step)) * step <= tol


def on_grid3(p: Sequence[float], step: float = MACRO_GRID) -> bool:
    return all(on_grid(v, step) for v in p)


def snap(value: float, step: float = MACRO_GRID) -> float:
    return quantize(value, grid=step)


# ---------------------------------------------------------------------------------- faces
@dataclass(frozen=True)
class Face:
    """A planar face of a mass. Corners p00, p10, p11, p01: `a` runs along p00→p10 (across the
    face, left to right as seen from outside, or front to back on the sides), `b` from that edge
    toward p01 (up, or back on top faces). Coordinates a, b are metres in the face plane."""

    host: str
    name: str
    corners: tuple[P3, P3, P3, P3]
    outward: P3

    @property
    def origin(self) -> P3:
        return self.corners[0]

    @property
    def axis_a(self) -> P3:
        return unit(sub(self.corners[1], self.corners[0]))

    @property
    def axis_b(self) -> P3:
        edge = sub(self.corners[3], self.corners[0])
        return unit(sub(edge, mul(self.axis_a, dot(edge, self.axis_a))))

    def at(self, a: float, b: float) -> P3:
        return add(self.origin, add(mul(self.axis_a, a), mul(self.axis_b, b)))

    def local(self, p: Sequence[float]) -> tuple[float, float]:
        d = sub(p, self.origin)
        return dot(d, self.axis_a), dot(d, self.axis_b)

    @property
    def width(self) -> float:
        """Length of the p00→p10 edge."""
        return length(sub(self.corners[1], self.corners[0]))

    @property
    def height(self) -> float:
        """Distance from the p00→p10 edge to the opposite edge, in the face plane."""
        return self.local(self.corners[3])[1]

    @property
    def center(self) -> P3:
        c = self.corners
        return mul(add(add(c[0], c[1]), add(c[2], c[3])), 0.25)

    def distance(self, p: Sequence[float]) -> float:
        """Signed distance from the face plane (+ outside)."""
        return dot(sub(p, self.origin), self.outward)

    def contains(self, p: Sequence[float], tol: float = 1e-6) -> bool:
        """p lies in the face plane and inside its (convex) outline."""
        if abs(self.distance(p)) > tol:
            return False
        pts = [self.local(c) for c in self.corners]
        q = self.local(p)
        sign = 0.0
        for i in range(4):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
            side = (x1 - x0) * (q[1] - y0) - (y1 - y0) * (q[0] - x0)
            if abs(side) <= tol:
                continue
            if sign and side * sign < 0:
                return False
            sign = side
        return True

    def rect(self, a0: float, a1: float, b0: float, b1: float, name: str = "") -> Region:
        return Region(self, a0, a1, b0, b1, name)

    def span(self, a_margin: float, b0: float, b1: float, name: str = "") -> Region:
        """Region across the face at heights b0..b1, `a_margin` in from both side edges — follows a
        slanted or tapered outline (side windows, windscreens)."""
        pts = [self.local(c) for c in self.corners]

        def a_limits(b: float) -> tuple[float, float]:
            xs = []
            for i in range(4):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
                if abs(y1 - y0) > 1e-9 and min(y0, y1) - 1e-9 <= b <= max(y0, y1) + 1e-9:
                    xs.append(x0 + (x1 - x0) * (b - y0) / (y1 - y0))
            return min(xs), max(xs)

        lo0, hi0 = a_limits(b0)
        lo1, hi1 = a_limits(b1)
        return Region(self, max(lo0, lo1) + a_margin, min(hi0, hi1) - a_margin, b0, b1, name)


@dataclass(frozen=True)
class Region:
    """A metric rectangle in a host face plane: the semantic place of a window, a door, a panel."""

    face: Face
    a0: float
    a1: float
    b0: float
    b1: float
    name: str = ""

    def __post_init__(self) -> None:
        if self.a1 - self.a0 <= 1e-9 or self.b1 - self.b0 <= 1e-9:
            raise ValueError(f"empty region {self.name!r} on {self.face.host}.{self.face.name}")

    @property
    def corners(self) -> tuple[P3, P3, P3, P3]:
        f = self.face
        return (f.at(self.a0, self.b0), f.at(self.a1, self.b0), f.at(self.a1, self.b1), f.at(self.a0, self.b1))

    @property
    def normal(self) -> P3:
        return self.face.outward

    @property
    def size(self) -> tuple[float, float]:
        return self.a1 - self.a0, self.b1 - self.b0

    def inset(self, d: float, name: str | None = None) -> Region:
        return Region(self.face, self.a0 + d, self.a1 - d, self.b0 + d, self.b1 - d, self.name if name is None else name)

    def grow(self, d: float) -> Region:
        return self.inset(-d)

    def split_a(self, count: int, gap: float, name: str = "") -> list[Region]:
        """`count` equal regions side by side along a, `gap` apart (a row of windows)."""
        w = (self.a1 - self.a0 - gap * (count - 1)) / count
        return [Region(self.face, self.a0 + i * (w + gap), self.a0 + i * (w + gap) + w, self.b0, self.b1,
                       f"{name or self.name}_{i}") for i in range(count)]

    def sub(self, ta0: float, ta1: float, tb0: float, tb1: float, name: str = "") -> Region:
        """A fraction of this region (0..1 along a and b)."""
        wa, wb = self.size
        return Region(self.face, self.a0 + wa * ta0, self.a0 + wa * ta1, self.b0 + wb * tb0, self.b0 + wb * tb1,
                      name or self.name)


# ---------------------------------------------------------------------------------- masses
_FACES_Z = {"bottom": (0, 1, 2, 3), "top": (4, 5, 6, 7), "front": (0, 1, 5, 4), "back": (2, 3, 7, 6),
            "left": (0, 3, 7, 4), "right": (1, 2, 6, 5)}
_FACES_Y = {"front": (0, 1, 2, 3), "back": (5, 4, 7, 6), "left": (0, 4, 7, 3), "right": (1, 5, 6, 2),
            "top": (3, 2, 6, 7), "bottom": (0, 1, 5, 4)}


@dataclass(frozen=True)
class Mass:
    """Convex hull between two parallel axis-aligned rectangles: BOX, WEDGE (sloped nose, tapered
    roof) or a tapered BEAM (tail boom). Corners 0–3 are the first section, 4–7 the second."""

    name: str
    corners: tuple[P3, ...]
    faces: dict = field(compare=False, repr=False)

    @classmethod
    def wedge(cls, name: str, bottom: Sequence[float], top: Sequence[float], z0: float, z1: float) -> Mass:
        """Sections along Z: bottom and top rectangles (x0, x1, y0, y1)."""
        def ring(r: Sequence[float], z: float) -> list[P3]:
            x0, x1, y0, y1 = r
            return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
        return cls(name, tuple(ring(bottom, z0) + ring(top, z1)), _FACES_Z)

    @classmethod
    def box(cls, name: str, lo: Sequence[float], hi: Sequence[float]) -> Mass:
        return cls.wedge(name, (lo[0], hi[0], lo[1], hi[1]), (lo[0], hi[0], lo[1], hi[1]), lo[2], hi[2])

    @classmethod
    def loft(cls, name: str, y0: float, y1: float, front: Sequence[float], back: Sequence[float]) -> Mass:
        """Sections along Y: front and back rectangles (x0, x1, z0, z1)."""
        def ring(r: Sequence[float], y: float) -> list[P3]:
            x0, x1, z0, z1 = r
            return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        return cls(name, tuple(ring(front, y0) + ring(back, y1)), _FACES_Y)

    @property
    def bounds(self) -> tuple[P3, P3]:
        return (tuple(min(c[i] for c in self.corners) for i in range(3)),  # type: ignore[return-value]
                tuple(max(c[i] for c in self.corners) for i in range(3)))

    @property
    def centroid(self) -> P3:
        return mul(tuple(sum(c[i] for c in self.corners) for i in range(3)), 1 / 8)  # type: ignore[arg-type]

    def face(self, name: str) -> Face:
        idx = self.faces[name]
        pts = tuple(self.corners[i] for i in idx)
        n = cross(sub(pts[1], pts[0]), sub(pts[3], pts[0]))
        if length(n) < 1e-12:
            n = cross(sub(pts[2], pts[1]), sub(pts[0], pts[1]))
        n = unit(n)
        if dot(n, sub(mul(add(add(pts[0], pts[1]), add(pts[2], pts[3])), 0.25), self.centroid)) < 0:
            n = mul(n, -1.0)
        return Face(self.name, name, pts, n)  # type: ignore[arg-type]

    def check_grid(self, bounds_step: float = MACRO_GRID, corner_step: float = DETAIL_GRID) -> None:
        """Bounds on `bounds_step` per axis; a thin member (a fin, a plate) may instead be centred
        on `bounds_step` with its faces on `corner_step`. Shaping corners on `corner_step`."""
        lo, hi = self.bounds
        for i in range(3):
            thin = hi[i] - lo[i] <= bounds_step + 1e-9 and on_grid((lo[i] + hi[i]) / 2, bounds_step)
            if not (on_grid(lo[i], bounds_step) and on_grid(hi[i], bounds_step)) and not thin:
                raise ValueError(f"mass {self.name}: bounds {lo}..{hi} off the {bounds_step} m grid on axis {'xyz'[i]}")
        for c in self.corners:
            if not on_grid3(c, corner_step):
                raise ValueError(f"mass {self.name}: corner {c} off the {corner_step} m grid")


# ---------------------------------------------------------------------------------- primitives
@dataclass
class Prim:
    """One drawable primitive: hull, cylinder, beam, panel, frame, lamp or wheel."""

    kind: str
    part: str
    group: str
    role: str
    color: str
    geo: dict
    name: str = ""
    asym: bool = False

    def points(self) -> list[P3]:
        g = self.geo
        if self.kind == "hull":
            return list(g["corners"])
        if self.kind == "cylinder":
            ax, (lo, hi), c, r = g["axis"], g["span"], g["center"], g["radius"]
            out = []
            if "phase" in g:                             # exact polygon of a turned (flat-bottomed) prism
                ring = [(c[0] + r * math.cos(g["phase"] + 2 * math.pi * k / g["sides"]),
                         c[1] + r * math.sin(g["phase"] + 2 * math.pi * k / g["sides"])) for k in range(g["sides"])]
                for t in (lo, hi):
                    for u, v in ring:
                        out.append({"x": (t, u, v), "y": (v, t, u), "z": (u, v, t)}[ax])
                return out
            for t in (lo, hi):
                for d0 in (-r, r):
                    for d1 in (-r, r):
                        p = {"x": (t, c[0] + d0, c[1] + d1), "y": (c[1] + d1, t, c[0] + d0),
                             "z": (c[0] + d0, c[1] + d1, t)}[ax]
                        out.append(p)
            return out
        if self.kind == "beam":
            r = max(g["width"], g["depth"]) / 2
            return [add(p, (dx, dy, dz)) for p in (g["p0"], g["p1"]) for dx in (-r, r) for dy in (-r, r) for dz in (-r, r)]
        if self.kind in ("panel", "frame"):
            region: Region = g["region"]
            reg = region.grow(g.get("width", 0.0)) if self.kind == "frame" else region
            n = region.normal
            lift = g.get("offset", 0.0)
            return [add(c, mul(n, lift + k * g["thickness"])) for c in reg.corners for k in (0, 1)]
        if self.kind == "lamp":
            s = g["size"]
            return [add(g["center"], (dx, dy, dz)) for dx in (-s, s) for dy in (-s, s) for dz in (-s, s)]
        if self.kind == "wheel":
            c, r, w = g["center"], g["radius"], g["width"]
            return [add(c, (dx, dy, dz)) for dx in (-w / 2, w / 2) for dy in (-r, r) for dz in (-r, r)]
        raise ValueError(self.kind)

    @property
    def bounds(self) -> tuple[P3, P3]:
        pts = self.points()
        return (tuple(min(p[i] for p in pts) for i in range(3)),  # type: ignore[return-value]
                tuple(max(p[i] for p in pts) for i in range(3)))


@dataclass
class Rotor:
    """Hub and blades on one spinning node: plane XY spins about Z, plane YZ about X. `look` is
    the stage of its detail; spinning is animation, independent of the stage."""

    name: str
    part: str
    group: str
    hub: P3
    plane: str
    radius: float
    blades: int
    chord: float
    look: int
    color: str
    tip: str | None
    hub_color: str
    turns: float
    phase: float = 0.0

    def tips(self) -> list[P3]:
        """Blade-tip corners at rest — the reach of the rotor for part isolation."""
        out = []
        half = self.chord / 2
        for i in range(self.blades):
            a = self.phase + 2 * math.pi * i / self.blades
            for e in (-1, 1):
                d, s = (self.radius * math.cos(a) - e * half * math.sin(a), self.radius * math.sin(a) + e * half * math.cos(a))
                off = (d, s, 0.0) if self.plane == "XY" else (0.0, d, s)
                out.append(add(self.hub, off))
        return out


class Plan:
    """The model at one stage: primitives filtered by role, plus the stage-independent skeleton
    (masses, faces, regions, ports) they were derived from."""

    def __init__(self, stage: int) -> None:
        if stage not in STAGES:
            raise ValueError(f"stage must be 1..5, got {stage}")
        self.stage = stage
        self.prims: list[Prim] = []
        self.rotors: list[Rotor] = []
        self.ports: dict[str, P3] = {}
        self.masses: dict[str, Mass] = {}
        self.regions: dict[str, Region] = {}

    # -- visibility
    def shows(self, role: str, until: int | None = None) -> bool:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        return ROLES[role] <= self.stage and (until is None or self.stage <= until)

    # -- skeleton
    def port(self, name: str, point: Sequence[float], step: float = MACRO_GRID) -> P3:
        p = (float(point[0]), float(point[1]), float(point[2]))
        if not on_grid3(p, step):
            raise ValueError(f"port {name} {p} is off the {step} m grid")
        self.ports[name] = p
        return p

    def region(self, region: Region) -> Region:
        if not region.name:
            raise ValueError("regions need a name")
        for c in region.corners:
            if not region.face.contains(c, tol=1e-6):
                raise ValueError(f"region {region.name} leaves face {region.face.host}.{region.face.name}")
        self.regions[region.name] = region
        return region

    # -- primitives
    def _add(self, kind: str, part: str, group: str, role: str, color: str, until: int | None, name: str,
             asym: bool, geo: dict) -> Prim | None:
        if not self.shows(role, until):
            return None
        prim = Prim(kind, part, group, role, color, geo, name, asym)
        self.prims.append(prim)
        return prim

    def mass(self, m: Mass, color: str, *, part: str, group: str | None = None, role: str = "mass",
             until: int | None = None, asym: bool = False) -> Mass:
        """Register a mass (its faces stay usable at every stage) and draw it while visible.
        Primary masses keep their bounds on MACRO_GRID; refining forms on DETAIL_GRID."""
        m.check_grid(MACRO_GRID if role == "mass" else DETAIL_GRID, DETAIL_GRID)
        self.masses[m.name] = m
        self._add("hull", part, group or m.name, role, color, until, m.name, asym, {"corners": m.corners})
        return m

    def cylinder(self, axis: str, span: Sequence[float], center: Sequence[float], radius: float, color: str, *,
                 part: str, group: str, role: str, sides: int = 12, until: int | None = None, name: str = "",
                 asym: bool = False, flat: bool = False) -> Prim | None:
        """Cylinder along `axis`; `center` holds the two other coordinates in x, y, z order
        (axis x: (y, z); axis y: (x, z); axis z: (x, y)). `flat` turns the polygon half a side so a
        flat face, not a corner, sits at `radius` below the centre (a tyre standing on the road)."""
        c = tuple(center)
        if axis == "y":                                  # stored as (z, x) for prim.points
            c = (c[1], c[0])
        geo = {"axis": axis, "span": tuple(span), "center": c, "radius": radius, "sides": sides}
        if flat:
            geo["radius"] = radius / math.cos(math.pi / sides)
            geo["phase"] = math.pi / sides
        return self._add("cylinder", part, group, role, color, until, name, asym, geo)

    def beam(self, p0: Sequence[float], p1: Sequence[float], width: float, depth: float, color: str, *, part: str,
             group: str, role: str, until: int | None = None, name: str = "", asym: bool = False) -> Prim | None:
        return self._add("beam", part, group, role, color, until, name, asym,
                         {"p0": tuple(p0), "p1": tuple(p1), "width": width, "depth": depth})

    def panel(self, region: Region, color: str, *, part: str, group: str, role: str, thickness: float = 0.015,
              offset: float = 0.0, until: int | None = None, asym: bool = False) -> Prim | None:
        """A plate lying on the region's face, `offset` above it, `thickness` outward."""
        return self._add("panel", part, group, role, color, until, region.name, asym,
                         {"region": region, "thickness": thickness, "offset": offset})

    def frame(self, region: Region, color: str, *, part: str, group: str, role: str, width: float = 0.04,
              thickness: float = 0.03, until: int | None = None, asym: bool = False) -> Prim | None:
        """A border lying on the face right outside the region edges (a window frame)."""
        for c in region.grow(width).corners:
            if not region.face.contains(c, tol=1e-6):
                raise ValueError(f"frame of {region.name} leaves face {region.face.host}.{region.face.name}")
        return self._add("frame", part, group, role, color, until, region.name, asym,
                         {"region": region, "width": width, "thickness": thickness})

    def lamp(self, center: Sequence[float], size: float, color: str, *, part: str, group: str, role: str = "accent",
             until: int | None = None, name: str = "", asym: bool = False) -> Prim | None:
        return self._add("lamp", part, group, role, color, until, name, asym, {"center": tuple(center), "size": size})

    def lamp_on(self, face: Face, size: float, color: str, *, part: str, group: str, at: Sequence[float] | None = None,
                role: str = "accent", name: str = "", asym: bool = False) -> Prim | None:
        """A lamp half sunk into a host face at face coordinates `at` (a, b); the face centre by default."""
        point = face.center if at is None else face.at(*at)
        return self.lamp(add(point, mul(face.outward, size * 0.5)), size, color, part=part, group=group, role=role,
                         name=name, asym=asym)

    def wheel(self, center: Sequence[float], radius: float, width: float, *, side: int, part: str, group: str,
              role: str = "mass", until: int | None = None, name: str = "") -> Prim | None:
        return self._add("wheel", part, group, role, "soot", until, name, False,
                         {"center": tuple(center), "radius": radius, "width": width, "side": side})

    def rotor(self, rotor: Rotor) -> Rotor:
        self.rotors.append(rotor)
        return rotor

    # -- queries
    def of_group(self, group: str, roles: Sequence[str] = ("mass", "form")) -> Iterator[Prim]:
        return (p for p in self.prims if p.group == group and p.role in roles)

    def bounds(self, prims: Sequence[Prim] | None = None) -> tuple[P3, P3]:
        pts = [pt for p in (self.prims if prims is None else prims) for pt in p.points()]
        return (tuple(min(p[i] for p in pts) for i in range(3)),  # type: ignore[return-value]
                tuple(max(p[i] for p in pts) for i in range(3)))
