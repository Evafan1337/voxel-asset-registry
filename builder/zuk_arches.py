"""Controlled Żuk arch study: small throats, real wheelhouses and crown caps.

The original ``open`` generators remain their own unchanged code paths. Stage 1
keeps their MACRO-grid tunnel and adds two plain wheelhouse boxes. Stages 2/3
refine that tunnel on DETAIL_GRID, with thin plates derived from the host faces.
All dimensions are in the common truck frame: X right, front -Y, Z up.
"""
from __future__ import annotations

from dataclasses import dataclass

import blockout as bo
import zuklib as zk
from blockout import Mass, Plan

D = bo.DETAIL_GRID
SIDES = ((-1, "left"), (1, "right"))


@dataclass(frozen=True)
class ArchGeometry:
    half_length: float
    top: float
    chamfer: float


@dataclass(frozen=True)
class FacetRegion(bo.Region):
    """A convex plate footprint in the existing host face plane.

    Its outline follows the two arch shoulder anchors. Plan.region still checks
    every corner against the real source face; this changes a panel footprint,
    without relaxing Mass grids or introducing a separate free-floating hull.
    """
    outline: tuple = ()

    @property
    def corners(self):
        return self.outline


def geometry(stage: int) -> ArchGeometry:
    """Keep the coarse box opening before introducing the smaller faceted throat."""
    return ArchGeometry(.5, 1., 0.) if stage == 1 else ArchGeometry(7 * D, 14 * D, 2 * D)


def refine_host(p: Plan, mass: Mass, axle_y: float, color: str, group: str) -> None:
    """Retain the source box, split its shell around the common arch profile."""
    p.mass(mass, color, part=group, group=group, until=0)
    lo, hi = mass.bounds
    profile = geometry(p.stage)
    half, top, chamfer = profile.half_length, profile.top, profile.chamfer
    role = "mass" if p.stage == 1 else "form"
    floor = zk.CHASSIS_HI[2]

    def section(name, y0, y1, z0, z1):
        a, b = max(lo[1], y0), min(hi[1], y1)
        if b <= a:
            return
        za = z0 + (z1 - z0) * (a - y0) / (y1 - y0)
        zb = z0 + (z1 - z0) * (b - y0) / (y1 - y0)
        if abs(za - zb) < 1e-9 and za < floor:
            p.mass(Mass.box(name + "_floor", (lo[0], a, floor), (hi[0], b, hi[2])),
                   color, part=group, group=group, role=role)
            for sx, side in SIDES:
                x = (lo[0], -.5) if sx < 0 else (.5, hi[0])
                p.mass(Mass.box(name + "_skirt_" + side, (x[0], a, za), (x[1], b, floor)),
                       color, part=group, group=group, role=role)
            return
        shape = (Mass.box(name, (lo[0], a, za), (hi[0], b, hi[2])) if abs(za - zb) < 1e-9 else
                 Mass.loft(name, a, b, (lo[0], hi[0], za, hi[2]), (lo[0], hi[0], zb, hi[2])))
        p.mass(shape, color, part=group, group=group, role=role)

    section(mass.name + "_before", lo[1], axle_y - half, lo[2], lo[2])
    if chamfer:
        section(mass.name + "_shoulder_front", axle_y - half, axle_y - half + chamfer,
                top - chamfer, top)
    section(mass.name + "_crown", axle_y - half + chamfer, axle_y + half - chamfer, top, top)
    if chamfer:
        section(mass.name + "_shoulder_rear", axle_y + half - chamfer, axle_y + half,
                top, top - chamfer)
    if group == "cab_shell" and p.stage >= 3:
        step_y = zk.CAB_HI[1] - 3 * D
        section(mass.name + "_after", axle_y + half, step_y, lo[2], lo[2])
        section(mass.name + "_step_upper", step_y, hi[1], floor, floor)
    else:
        section(mass.name + "_after", axle_y + half, hi[1], lo[2], lo[2])


def _face_box(p: Plan, host: Mass, face_name: str, lo, hi, color: str, name: str, group: str) -> None:
    """A thin box positioned by a real host face and its common axle-derived region.

    Plate thickness and embedding are face offsets, not a relaxed Mass grid.
    Negative offsets put the liner inside its source shell; cap mounting plates
    bridge the outer visor to the surviving crown above the opening.
    """
    face = host.face(face_name)
    axis = max(range(3), key=lambda k: abs(face.outward[k]))
    sign = face.outward[axis]
    plane = face.center[axis]
    corners = []
    tangents = [k for k in range(3) if k != axis]
    for u in (lo[tangents[0]], hi[tangents[0]]):
        for v in (lo[tangents[1]], hi[tangents[1]]):
            point = list(lo)
            point[axis] = plane
            point[tangents[0]], point[tangents[1]] = u, v
            corners.append(face.local(point))
    region = p.region(face.rect(min(c[0] for c in corners), max(c[0] for c in corners),
                                min(c[1] for c in corners), max(c[1] for c in corners), name))
    nearest = lo[axis] if sign > 0 else hi[axis]
    p.panel(region, color, part=group, group=group, role="form",
            offset=sign * (nearest - plane), thickness=hi[axis] - lo[axis])


def _shoulder_lip(p: Plan, host: Mass, side: str, axle_y: float, end: int, color: str) -> None:
    """Short exterior 45-degree plate joined to both crown visor and top mount."""
    face = host.face(side)
    profile = geometry(p.stage)
    crown_half = profile.half_length - profile.chamfer
    inner_y = axle_y + end * crown_half
    outer_y = axle_y + end * profile.half_length
    plane = face.center[0]
    lower, upper = 11.5 * D, 15 * D
    points = ((plane, inner_y, lower), (plane, outer_y, lower - profile.chamfer),
              (plane, outer_y, upper - profile.chamfer), (plane, inner_y, upper))
    normal = bo.cross(bo.sub(points[1], points[0]), bo.sub(points[3], points[0]))
    if bo.dot(normal, face.outward) < 0:
        points = tuple(reversed(points))
    local = [face.local(point) for point in points]
    name = "arch_cap_shoulder_" + ("front" if end < 0 else "rear") + "_" + side
    region = p.region(FacetRegion(face, min(a for a, b in local), max(a for a, b in local),
                                  min(b for a, b in local), max(b for a, b in local), name, points))
    p.panel(region, color, part="arch_caps", group="arch_caps", role="form",
            offset=D / 4, thickness=3 * D / 4)


def add_wheelhouse(p: Plan, host: Mass, axle_y: float, balance: str, liner_color: str, cap_color: str) -> None:
    """Add one physically connected wheelhouse per side, and an optional crown cap."""
    if balance not in {"mini_cap", "liner_only"}:
        raise ValueError(f"unknown arch balance {balance!r}")
    if p.stage == 1:
        for sx, side in SIDES:
            x = (-.5, -.25) if sx < 0 else (.25, .5)
            p.mass(Mass.box("arch_liner_box_" + side, (x[0], axle_y - .5, .75),
                            (x[1], axle_y + .5, 1.)), liner_color,
                   part="arch_liners", group="arch_liners")
        return

    def mirrored(sx, a, b):
        return (-b, -a) if sx < 0 else (a, b)

    # Continuous-cylinder yaw/bump bounds: inner |X| >= .5042809,
    # outer |X| <= .9957191, |Y-axle| <= .3952847, highest Z <= .8125.
    # These faces retain >=19.9 mm lateral, >=26.5 mm longitudinal and
    # >=46.8 mm vertical clearance. Their ceiling embeds above the .875 crown.
    for sx, side in SIDES:
        inner_x = mirrored(sx, 7.5 * D, 7.75 * D)
        whole_x = mirrored(sx, 7.5 * D, 15.75 * D)
        y = (axle_y - 7.25 * D, axle_y + 7.25 * D)
        z0, ceiling_z0, ceiling_z1 = 12.25 * D, 13.75 * D, 14.5 * D
        _face_box(p, host, side, (inner_x[0], y[0], z0), (inner_x[1], y[1], ceiling_z0),
                  liner_color, "arch_liner_inner_" + side, "arch_liners")
        _face_box(p, host, "bottom", (whole_x[0], y[0], ceiling_z0),
                  (whole_x[1], y[1], ceiling_z1), liner_color,
                  "arch_liner_ceiling_" + side, "arch_liners")
        for end, direction in ((-1, "front"), (1, "back")):
            ya, yb = sorted((axle_y + end * 6.75 * D, axle_y + end * 7.25 * D))
            _face_box(p, host, direction, (whole_x[0], ya, z0), (whole_x[1], yb, ceiling_z0),
                      liner_color, "arch_liner_" + direction + "_" + side, "arch_liners")
        if balance == "mini_cap":
            cap_y = (axle_y - 5 * D, axle_y + 5 * D)
            visor_x = mirrored(sx, 16.25 * D, 17 * D)
            mount_x = mirrored(sx, 15.75 * D, 17 * D)
            _face_box(p, host, side, (visor_x[0], cap_y[0], 11.5 * D),
                      (visor_x[1], cap_y[1], 14 * D), cap_color,
                      "arch_cap_visor_" + side, "arch_caps")
            _face_box(p, host, side, (mount_x[0], cap_y[0], 14 * D),
                      (mount_x[1], cap_y[1], 15 * D), cap_color,
                      "arch_cap_mount_" + side, "arch_caps")
            for end in (-1, 1):
                _shoulder_lip(p, host, side, axle_y, end, cap_color)


def accessory_key(prim) -> str | None:
    """Aggregate the connected plates of each side as one semantic export mesh."""
    if prim.group not in {"arch_caps", "arch_liners"}:
        return None
    kind = "arch_cap" if prim.group == "arch_caps" else "arch_liner"
    return kind + "_" + prim.name.rsplit("_", 1)[1]
