"""Shared geometry for vehicles (vh_*): stage-driven wheels and rotors, lofted hulls, part isolation,
and render() — the Blender side of a blockout.Plan (masses, regions, ports; see builder/blockout.py).

Vehicles face −Y (glTF +Z), stand on z = 0 and grow in `stage` 1…5 — the same model from a
blockout to the game model. `part` builds only one key block, centred and standing on the ground,
for evolution showcases. Changing this file changes every vh_* generator: bump their
generator_version."""

from __future__ import annotations

import math
from typing import Callable, Sequence

from mathutils import Vector

import voxlib as vx

Vec = Sequence[float]


def hexa(m: vx.MeshBuilder, pts: Sequence[Vec], color: str) -> None:
    """Convex hexahedron from 8 corners: 0–3 around one end, 4–7 the same way around the other."""
    p = [Vector(v) for v in pts]
    centre = sum(p, Vector()) / 8
    for face in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        f = [p[i] for i in face]
        normal = (f[1] - f[0]).cross(f[2] - f[0])
        if normal.length < 1e-9:
            normal = (f[2] - f[0]).cross(f[3] - f[0])
        mid = sum(f, Vector()) / 4
        m.polygon([tuple(v) for v in (f if normal.dot(mid - centre) >= 0 else reversed(f))], color)


def loft(m: vx.MeshBuilder, y0: float, y1: float, a: tuple[float, float, float], b: tuple[float, float, float],
         color: str) -> None:
    """A hull section between two cross-sections along Y. a, b = (half_width, z_bottom, z_top)
    at y0 and y1: a box that can taper and tilt (noses, windscreens, tail booms)."""
    def ring(y: float, s: tuple[float, float, float]) -> list[Vector]:
        w, z0, z1 = s
        return [Vector((-w, y, z0)), Vector((w, y, z0)), Vector((w, y, z1)), Vector((-w, y, z1))]
    hexa(m, ring(y0, a) + ring(y1, b), color)


def panel(m: vx.MeshBuilder, corners: Sequence[Vec], normal: Vec, thickness: float, color: str) -> None:
    """Thin plate on a planar quad (glass, doors, panels), extruded along `normal`."""
    n = Vector(normal).normalized() * thickness
    base = [Vector(c) for c in corners]
    hexa(m, base + [c + n for c in base], color)


def wheel(m: vx.MeshBuilder, centre: Vec, r: float, width: float, stage: int, *, side: int = 1,
          tire: str = "soot", rim: str = "steel", hub: str = "steel_dark") -> None:
    """Wheel on an axle along X; `side` +1 puts the rim face at +X. Grows with the stage:
    block → octagon with a rim → 12 sides with a hub → 16 sides with nuts → sidewall ring."""
    c = Vector(centre)
    x0, x1 = c.x - width / 2, c.x + width / 2
    if stage <= 1:
        m.box((x0, c.y - r * 0.9, c.z - r), (x1, c.y + r * 0.9, c.z + r * 0.9), tire)
        return
    sides = {2: 8, 3: 12}.get(stage, 16)
    # a flat facet at the bottom: the apothem equals r, so the tyre stands on c.z - r
    m.prism(r / math.cos(math.pi / sides), x0, x1, tire, sides=sides, center=(c.y, c.z), axis="X",
            phase=math.pi / sides)
    face = c.x + side * width / 2
    lo, hi = sorted((face - side * 0.01, face + side * 0.015))
    m.prism(r * 0.6, lo, hi, rim, sides=sides, center=(c.y, c.z), axis="X", phase=math.pi / sides)
    if stage >= 3:
        lo, hi = sorted((face, face + side * 0.05))
        m.prism(r * 0.22, lo, hi, hub, sides=8, center=(c.y, c.z), axis="X")
    if stage >= 4:
        for i in range(6):
            a = 2 * math.pi * i / 6
            y, z = c.y + r * 0.36 * math.cos(a), c.z + r * 0.36 * math.sin(a)
            lo, hi = sorted((face, face + side * 0.035))
            m.box((lo, y - 0.018, z - 0.018), (hi, y + 0.018, z + 0.018), hub)
    if stage >= 5:                                                     # sidewall ring
        lo, hi = sorted((face - side * 0.005, face + side * 0.01))
        ring_x(m, c, r * 0.74, r * 0.8, lo, hi, hub, sides)


def ring_x(m: vx.MeshBuilder, centre: Vec, r0: float, r1: float, x0: float, x1: float, color: str,
           sides: int = 16) -> None:
    """Annulus around an axis along X through `centre` (y, z taken from it)."""
    c = Vector(centre)
    for i in range(sides):
        a0, a1 = 2 * math.pi * i / sides, 2 * math.pi * (i + 1) / sides
        ring = [(r0, a0), (r1, a0), (r1, a1), (r0, a1)]
        hexa(m, [(x, c.y + r * math.cos(a), c.z + r * math.sin(a)) for x in (x0, x1) for r, a in ring], color)


def blade(m: vx.MeshBuilder, hub_r: float, radius: float, angle: float, chord: float, thick: float, color: str,
          tip: str | None, *, plane: str = "XY") -> None:
    """One flat rotor blade from hub_r to radius at `angle`, in the XY plane (main rotor) or the
    YZ plane (tail rotor spinning about X)."""
    def at(d: float) -> Vector:
        if plane == "XY":
            return Vector((d * math.cos(angle), d * math.sin(angle), 0.0))
        return Vector((0.0, d * math.cos(angle), d * math.sin(angle)))
    split = radius * 0.86 if tip else radius
    w, dp = (chord, thick) if plane == "XY" else (thick, chord)
    m.strut(tuple(at(hub_r)), tuple(at(split)), w, color, depth=dp)
    if tip:
        m.strut(tuple(at(split)), tuple(at(radius)), w, tip, depth=dp)


def rotor(parent: "bpy.types.Object", name: str, location: Vec, *, radius: float, blades: int,  # noqa: F821
          chord: float, stage: int, color: str, tip: str | None, hub_color: str, turns: float,
          plane: str = "XY", phase: float = 0.0, semantic: str = "rotor") -> "bpy.types.Object":  # noqa: F821
    """Hub and blades as one node spinning about Z (plane XY) or X (plane YZ)."""
    m = vx.MeshBuilder()
    hub_r = radius * (0.1 if plane == "XY" else 0.16)
    axis = "Z" if plane == "XY" else "X"
    thick = max(0.03, chord * 0.18)
    for i in range(blades):
        blade(m, hub_r * 0.8, radius, phase + 2 * math.pi * i / blades, chord, thick, color, tip, plane=plane)
    if stage <= 1:
        s = hub_r
        m.box((-s, -s, -s * 0.8), (s, s, s * 0.8), hub_color)
    else:
        m.prism(hub_r, -hub_r * 0.7, hub_r * 0.7, hub_color, sides=blades * 2 if blades > 2 else 8, axis=axis)
    if stage >= 3:                                                     # blade grips
        for i in range(blades):
            a = phase + 2 * math.pi * i / blades
            blade(m, hub_r * 0.7, hub_r * 1.9, a, chord * 1.25, thick * 2.2, hub_color, None, plane=plane)
    if stage >= 4:                                                     # cap and dampers
        if plane == "XY":
            m.prism(hub_r * 0.45, hub_r * 0.7, hub_r * 1.4, hub_color, sides=8)
            for i in range(blades):
                a = phase + 2 * math.pi * (i + 0.5) / blades
                m.strut((hub_r * 0.8 * math.cos(a), hub_r * 0.8 * math.sin(a), 0.0),
                        (hub_r * 1.6 * math.cos(a), hub_r * 1.6 * math.sin(a), hub_r * 0.3), 0.04, "steel", depth=0.04)
        else:
            m.prism(hub_r * 0.45, hub_r * 0.7, hub_r * 1.3, hub_color, sides=8, axis="X")
    obj = m.to_object(name, parent=parent, location=tuple(location), semantic_part=semantic)
    if vx.level() >= 3 and turns:
        vx.spin_animation(obj, name=f"{name}_spin", axis=2 if plane == "XY" else 0, turns=turns)
    return obj


class Parts:
    """Static geometry grouped by key block. part = "all" builds the whole vehicle; any other
    name builds only that block, shifted to stand centred on the ground (key-block showcases)."""

    def __init__(self, selected: str) -> None:
        self.selected = selected
        self.builders: dict[str, vx.MeshBuilder] = {}
        self.shift = Vector()

    def wants(self, name: str) -> bool:
        return self.selected in ("all", name)

    def mesh(self, name: str) -> vx.MeshBuilder:
        return self.builders.setdefault(name, vx.MeshBuilder())

    def finish(self, order: Sequence[str], extra: Sequence[Vec] = (), origin: Vec | None = None
               ) -> "bpy.types.Object":  # noqa: F821
        """`extra` — vehicle-space points of moving parts (blade tips) that must stay above ground.
        `origin` — a vehicle-space point that becomes the object origin (a block of a kit built
        around its mount point)."""
        names = [n for n in order if n in self.builders and self.builders[n].verts]
        if not names:
            raise ValueError(f"part {self.selected!r} produced no geometry")
        if origin is not None:
            self.shift = -Vector(origin)
            for n in names:
                b = self.builders[n]
                b.verts = [(x + self.shift.x, y + self.shift.y, z + self.shift.z) for x, y, z in b.verts]
        elif self.selected != "all":
            pts = [Vector(v) for n in names for v in self.builders[n].verts] + [Vector(v) for v in extra]
            lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            self.shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
            for n in names:
                b = self.builders[n]
                b.verts = [(x + self.shift.x, y + self.shift.y, z + self.shift.z) for x, y, z in b.verts]
        root = self.builders[names[0]].to_object(names[0], semantic_part=names[0])
        for n in names[1:]:
            self.builders[n].to_object(n, parent=root, semantic_part=n)
        return root

    def at(self, point: Vec) -> tuple[float, float, float]:
        """A vehicle-space point in the (possibly shifted) output space, for moving nodes."""
        return tuple(Vector(point) + self.shift)


def box(m: vx.MeshBuilder, a: Vec, b: Vec, color: str) -> None:
    """Box between any two opposite corners (mirrored sides may swap min and max)."""
    m.box(tuple(min(p, q) for p, q in zip(a, b)), tuple(max(p, q) for p, q in zip(a, b)), color)


def lights(m: vx.MeshBuilder, spots: Sequence[tuple[Vec, float, str]]) -> None:
    """Small cube lamps: (centre, size, color)."""
    for c, s, color in spots:
        m.box((c[0] - s, c[1] - s, c[2] - s), (c[0] + s, c[1] + s, c[2] + s), color)


def repeat(n: int, fn: Callable[[int], None]) -> None:
    for i in range(n):
        fn(i)


# ---------------------------------------------------------------------------------- plans
def draw(m: vx.MeshBuilder, prim, stage: int) -> None:  # noqa: ANN001
    """Draw one blockout.Prim into a mesh builder."""
    g = prim.geo
    if prim.kind == "hull":
        hexa(m, g["corners"], prim.color)
    elif prim.kind == "cylinder":
        axis = g["axis"].upper()
        lo, hi = g["span"]
        m.prism(g["radius"], lo, hi, prim.color, sides=g["sides"], center=g["center"], axis=axis,
                phase=g.get("phase", 0.0))
    elif prim.kind == "beam":
        m.strut(g["p0"], g["p1"], g["width"], prim.color, depth=g["depth"])
    elif prim.kind == "panel":
        r = g["region"]
        n = Vector(r.normal)
        base = [Vector(c) + n * g["offset"] for c in r.corners]
        panel(m, base, r.normal, g["thickness"], prim.color)
    elif prim.kind == "frame":
        r, w = g["region"], g["width"]
        f = r.face
        for a0, a1, b0, b1 in ((r.a0 - w, r.a1 + w, r.b0 - w, r.b0), (r.a0 - w, r.a1 + w, r.b1, r.b1 + w),
                               (r.a0 - w, r.a0, r.b0, r.b1), (r.a1, r.a1 + w, r.b0, r.b1)):
            strip = f.rect(a0, a1, b0, b1, r.name)
            panel(m, strip.corners, r.normal, g["thickness"], prim.color)
    elif prim.kind == "lamp":
        lights(m, [(g["center"], g["size"], prim.color)])
    elif prim.kind == "wheel":
        wheel(m, g["center"], g["radius"], g["width"], stage, side=g["side"])
    else:
        raise ValueError(f"unknown primitive {prim.kind}")


def render(plan, part: str = "all", origin: Vec | None = None, sockets: dict | None = None
           ) -> "bpy.types.Object":  # noqa: ANN001, F821
    """Draw a blockout.Plan: static primitives grouped by key block (`part`), rotors as spinning
    nodes, ports as sockets. An isolated part is centred on the ground, rotor reach included.
    `origin` moves the object origin to that plan point; `sockets` {port: (type, rotation_deg)}
    types and turns the sockets made from ports (generic, unturned by default)."""
    P = Parts(part)
    order: list[str] = []
    for prim in plan.prims:
        if P.wants(prim.part):
            draw(P.mesh(prim.part), prim, plan.stage)
            if prim.part not in order:
                order.append(prim.part)
    rotors = [r for r in plan.rotors if P.wants(r.part)]
    extra = [tip for r in rotors for tip in r.tips()] if part != "all" else []
    root = P.finish(order, extra=extra, origin=origin)
    for r in rotors:
        rotor(root, r.name, P.at(r.hub), radius=r.radius, blades=r.blades, chord=r.chord, stage=r.look,
              color=r.color, tip=r.tip, hub_color=r.hub_color, turns=r.turns, plane=r.plane, phase=r.phase)
    if part == "all":
        for name, point in plan.ports.items():
            kind, turn = (sockets or {}).get(name, ("generic", (0.0, 0.0, 0.0)))
            vx.socket(name, P.at(point), turn, parent=root, type=kind)
    return root
