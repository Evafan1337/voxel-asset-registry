"""Zuk study cab in truck space; front -Y, Z up, one fixed boxy skeleton.

Study stage 2 draws a real square clearance rather than a dark decal. Stage 3
adds only the cab's D11/D12/D13 families. Lamps remain reusable socket children.
"""
from __future__ import annotations

from typing import Any

import blockout as bo
import zuk_arches as za
import zuklib as zk
from blockout import Mass, Plan

D = bo.DETAIL_GRID
SIDES = ((-1, "left"), (1, "right"))


def _box(name, lo, hi):
    return Mass.box(name, lo, hi)


def _clearance(p, mass, axle_y, color, group):
    """Refine a solid into an upper host and lower core/side strips.

    The side cut is driven by the same axle as the reusable running gear.
    Clipping also removes the small back corner of the nose where necessary.
    """
    p.mass(mass, color, part=group, group=group, until=1)
    lo, hi = mass.bounds
    top = min(hi[2], zk.ARCH_TOP)
    if hi[2] > top:
        p.mass(_box(mass.name + "_upper", (lo[0], lo[1], top), hi), color,
               part=group, group=group, role="form")
    p.mass(_box(mass.name + "_core", (-zk.ARCH_INNER_X, lo[1], lo[2]),
                (zk.ARCH_INNER_X, hi[1], top)), color,
           part=group, group=group, role="form")
    outside = ((lo[1], min(hi[1], axle_y - zk.ARCH_HALF_LENGTH)),
               (max(lo[1], axle_y + zk.ARCH_HALF_LENGTH), hi[1]))
    for sx, side in SIDES:
        x = (lo[0], -zk.ARCH_INNER_X) if sx < 0 else (zk.ARCH_INNER_X, hi[0])
        for end, (y0, y1) in enumerate(outside):
            if y1 <= y0:
                continue
            p.mass(_box(f"{mass.name}_{side}_{end}", (x[0], y0, lo[2]), (x[1], y1, top)),
                   color, part=group, group=group, role="form")


def _inset_clearance(p, mass, axle_y, color, group, profile):
    """A true whole-width opening; no hidden centre slab fills its side view."""
    p.mass(mass, color, part=group, group=group, until=0)
    lo, hi = mass.bounds
    half, top = profile.arch_half_length, profile.arch_top
    role = "mass" if p.stage == 1 else "form"

    def section(name, y0, y1, z0, z1):
        a, b = max(lo[1], y0), min(hi[1], y1)
        if b <= a:
            return
        za = z0 + (z1 - z0) * (a - y0) / (y1 - y0)
        zb = z0 + (z1 - z0) * (b - y0) / (y1 - y0)
        if abs(za - zb) < 1e-9 and za < zk.CHASSIS_HI[2]:
            floor = zk.CHASSIS_HI[2]
            p.mass(_box(name + "_floor", (lo[0], a, floor), (hi[0], b, hi[2])), color,
                   part=group, group=group, role=role)
            for sx, side in SIDES:
                x = (lo[0], -.5) if sx < 0 else (.5, hi[0])
                p.mass(_box(name + "_skirt_" + side, (x[0], a, za), (x[1], b, floor)),
                       color, part=group, group=group, role=role)
            return
        shape = (_box(name, (lo[0], a, za), (hi[0], b, hi[2])) if abs(za - zb) < 1e-9 else
                 Mass.loft(name, a, b, (lo[0], hi[0], za, hi[2]), (lo[0], hi[0], zb, hi[2])))
        p.mass(shape, color, part=group, group=group, role=role)

    section(mass.name + "_before", lo[1], axle_y - half, lo[2], lo[2])
    chamfer = profile.arch_chamfer if p.stage >= 2 else 0.
    if chamfer:
        section(mass.name + "_shoulder_front", axle_y - half, axle_y - half + chamfer,
                top - chamfer, top)
    section(mass.name + "_crown", axle_y - half + chamfer, axle_y + half - chamfer, top, top)
    if chamfer:
        section(mass.name + "_shoulder_rear", axle_y + half - chamfer, axle_y + half,
                top, top - chamfer)
    # D18 reveals the rail-supported tread in the lower rear cab corner.
    if group == "cab_shell" and p.stage >= 3:
        step_y = zk.CAB_HI[1] - 3 * D
        section(mass.name + "_after", axle_y + half, step_y, lo[2], lo[2])
        section(mass.name + "_step_upper", step_y, hi[1], zk.CHASSIS_HI[2], zk.CHASSIS_HI[2])
    else:
        section(mass.name + "_after", axle_y + half, hi[1], lo[2], lo[2])


def _side_region(p, host, side, y, z, name):
    face = host.face(side)
    x = face.center[0]
    a = sorted(face.local((x, value, z[0]))[0] for value in y)
    b = sorted(face.local((x, y[0], value))[1] for value in z)
    return p.region(face.rect(*a, *b, name))


def plan(params: dict[str, Any]) -> Plan:
    stage = int(params.get("stage", 3))
    p = Plan(stage)
    col = lambda role: zk.color(stage, role, params.get("paint", "paint_gray"), params.get("finish", True))
    profile = zk.layout(params)
    inset = params.get("wheel_fit", "legacy") == "inset"
    balance = params.get("arch_balance", "open") if inset else "open"
    bottom = lambda point: (point[0], point[1], profile.body_bottom)
    cab = _box("cab", bottom(zk.CAB_LO), zk.CAB_HI)
    nose = _box("nose", bottom(zk.NOSE_LO), zk.NOSE_HI)
    if inset and balance != "open":
        za.refine_host(p, cab, zk.AXLES["front"], col("paint"), "cab_shell")
        za.refine_host(p, nose, zk.AXLES["front"], col("paint"), "nose")
        za.add_wheelhouse(p, cab, zk.AXLES["front"], balance, col("trim"), col("paint"))
    elif inset:
        _inset_clearance(p, cab, zk.AXLES["front"], col("paint"), "cab_shell", profile)
        _inset_clearance(p, nose, zk.AXLES["front"], col("paint"), "nose", profile)
    else:
        _clearance(p, cab, zk.AXLES["front"], col("paint"), "cab_shell")
        _clearance(p, nose, zk.AXLES["front"], col("paint"), "nose")
    for name, point in zk.FRONT_LAMPS.items():
        p.port(name, point, step=D)

    front = cab.face("front")
    shield = p.region(front.rect(2 * D, front.width - 2 * D,
                                 zk.NOSE_HI[2] - profile.body_bottom + 2 * D,
                                 front.height - 2 * D, "windscreen"))
    p.panel(shield, col("glass"), part="windscreen", group="windscreen", role="form",
            thickness=.015, offset=0.)

    for sx, side in SIDES:
        y = (zk.CAB_LO[1] + 2 * D, zk.CAB_HI[1] - 2 * D)
        door = _side_region(p, cab, side, y, (zk.ARCH_TOP + D, zk.CAB_HI[2] - 2 * D), f"door_{side}")
        window = _side_region(p, cab, side, (y[0] + 2 * D, y[1] - 4 * D),
                              (zk.CAB_LO[2] + 1., zk.CAB_HI[2] - 3 * D), f"window_{side}")
        p.frame(door, col("trim"), part="cab_doors", group="cab_doors", role="form",
                width=D / 4, thickness=.01)
        p.panel(window, col("glass"), part="side_windows", group="side_windows", role="form",
                thickness=.015, offset=0.)
        handle = _side_region(p, cab, side, (y[1] - 5 * D, y[1] - 2 * D),
                              (zk.CAB_LO[2] + .75, zk.CAB_LO[2] + .75 + D), f"handle_{side}")
        p.panel(handle, col("metal"), part="cab_handles", group="cab_handles", role="structure",
                offset=0., thickness=.04)

        face = cab.face(side)
        mount = face.at(*face.local((sx, zk.CAB_LO[1] + D, zk.CAB_LO[2] + 1.125)))
        head_x = (1. + D, 1. + 3 * D) if sx > 0 else (-1. - 3 * D, -1. - D)
        head = _box(f"mirror_{side}", (head_x[0], mount[1] - D, mount[2] - 2 * D),
                    (head_x[1], mount[1] + D, mount[2] + 2 * D))
        p.mass(head, col("metal"), part="mirrors", group="mirrors", role="structure")
        inner = head.face("left" if sx > 0 else "right")
        p.beam(mount, inner.center, D / 2, D / 2, col("metal"), part="mirrors", group="mirrors",
               role="structure", name=f"mirror_stem_{side}")

    lift = bo.mul(front.outward, .015)
    for sx, side in SIDES:
        a = front.width / 2 + sx * .5
        p.beam(bo.add(front.at(a, shield.b0 + D), lift),
               bo.add(front.at(a - sx * 4 * D, shield.b0 + 4 * D), lift),
               D / 4, D / 4, col("trim"), part="wipers", group="wipers", role="structure", name=f"wiper_{side}")

    face = nose.face("front")
    grille = p.region(face.rect(.5, face.width - .5,
                                1. - profile.body_bottom, 1.25 - profile.body_bottom, "grille"))
    p.panel(grille, col("trim"), part="grille", group="grille", role="form", thickness=.01)
    for k in range(3):
        bar = p.region(grille.sub(.0625, .9375, (k + .25) / 3, (k + .65) / 3, f"grille_bar_{k}"))
        p.panel(bar, col("metal"), part="grille_bars", group="grille_bars", role="form",
                offset=.0075, thickness=.0175)
    return p


def build(params: dict[str, Any]):
    import vehlib
    import voxlib as vx

    p = plan(params)
    origin = zk.ANCHORS["cab"]
    root = vx.empty("zk_cab")
    primary = {}
    accessories = {}
    for prim in p.prims:
        key = za.accessory_key(prim)
        mesh = (primary.setdefault(prim.group, vx.MeshBuilder()) if prim.group in {"cab_shell", "nose"} else
                accessories.setdefault(key, (prim.group, vx.MeshBuilder()))[1] if key else vx.MeshBuilder())
        vehlib.draw(mesh, prim, p.stage)
        if prim.group in primary or key:
            continue
        mesh.verts = [bo.sub(point, origin) for point in mesh.verts]
        mesh.to_object(prim.name, parent=root, semantic_part=prim.group)
    for group, mesh in primary.items():
        # A tiny join clearance avoids overlapping seam faces without moving anchors.
        mesh.verts = [(x - origin[0], (y - .001 if group == "cab_shell" and abs(y - zk.CAB_HI[1]) < 1e-8 else y) - origin[1],
                       z - origin[2]) for x, y, z in mesh.verts]
        mesh.to_object(group, parent=root, semantic_part=group)
    for name, (group, mesh) in accessories.items():
        mesh.verts = [bo.sub(point, origin) for point in mesh.verts]
        mesh.to_object(name, parent=root, semantic_part=group)
    for name, point in p.ports.items():
        vx.socket(name, bo.sub(point, origin), (90., 0., 0.), parent=root, type="vehicle_lamp")
    return root
