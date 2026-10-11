"""Closed Zuk cargo host: fixed box, square clearances, functional rear/side fields."""
from __future__ import annotations

from typing import Any

import blockout as bo
import zuk_arches as za
import zuklib as zk
from blockout import Mass, Plan

D = bo.DETAIL_GRID
SIDES = ((-1, "left"), (1, "right"))


def _inset_clearance(p, mass, axle_y, color, profile):
    """Split a host around an open tunnel; facet only the upper shoulders."""
    p.mass(mass, color, part="cargo", group="cargo", until=0)
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
            p.mass(Mass.box(name + "_floor", (lo[0], a, floor), (hi[0], b, hi[2])), color,
                   part="cargo", group="cargo", role=role)
            for sx, side in SIDES:
                x = (lo[0], -.5) if sx < 0 else (.5, hi[0])
                p.mass(Mass.box(name + "_skirt_" + side, (x[0], a, za), (x[1], b, floor)),
                       color, part="cargo", group="cargo", role=role)
            return
        shape = (Mass.box(name, (lo[0], a, za), (hi[0], b, hi[2])) if abs(za - zb) < 1e-9 else
                 Mass.loft(name, a, b, (lo[0], hi[0], za, hi[2]), (lo[0], hi[0], zb, hi[2])))
        p.mass(shape, color, part="cargo", group="cargo", role=role)

    section(mass.name + "_before", lo[1], axle_y - half, lo[2], lo[2])
    chamfer = profile.arch_chamfer if p.stage >= 2 else 0.
    if chamfer:
        section(mass.name + "_shoulder_front", axle_y - half, axle_y - half + chamfer,
                top - chamfer, top)
    section(mass.name + "_crown", axle_y - half + chamfer, axle_y + half - chamfer, top, top)
    if chamfer:
        section(mass.name + "_shoulder_rear", axle_y + half - chamfer, axle_y + half,
                top, top - chamfer)
    section(mass.name + "_after", axle_y + half, hi[1], lo[2], lo[2])


def _side_region(p, host, side, y, z, name):
    face = host.face(side)
    x = face.center[0]
    a = sorted(face.local((x, value, z[0]))[0] for value in y)
    b = sorted(face.local((x, y[0], value))[1] for value in z)
    return p.region(face.rect(*a, *b, name))


def _back_region(p, host, x, z, name):
    face = host.face("back")
    a = sorted(face.local((value, face.center[1], z[0]))[0] for value in x)
    b = sorted(face.local((x[0], face.center[1], value))[1] for value in z)
    return p.region(face.rect(*a, *b, name))


def plan(params: dict[str, Any]) -> Plan:
    stage = int(params.get("stage", 3))
    p = Plan(stage)
    col = lambda role: zk.color(stage, role, params.get("paint", "paint_gray"), params.get("finish", True))
    profile = zk.layout(params)
    body = Mass.box("cargo", (zk.BODY_LO[0], zk.BODY_LO[1], profile.body_bottom), zk.BODY_HI)
    lo, hi = body.bounds
    inset = params.get("wheel_fit", "legacy") == "inset"
    balance = params.get("arch_balance", "open") if inset else "open"
    if inset and balance != "open":
        za.refine_host(p, body, zk.AXLES["rear"], col("paint"), "cargo")
        za.add_wheelhouse(p, body, zk.AXLES["rear"], balance, col("trim"), col("paint"))
    elif inset:
        _inset_clearance(p, body, zk.AXLES["rear"], col("paint"), profile)
    else:
        p.mass(body, col("paint"), part="cargo", group="cargo", until=1)
        p.mass(Mass.box("cargo_upper", (lo[0], lo[1], zk.ARCH_TOP), hi), col("paint"),
               part="cargo", group="cargo", role="form")
        p.mass(Mass.box("cargo_core", (-zk.ARCH_INNER_X, lo[1], lo[2]),
                        (zk.ARCH_INNER_X, hi[1], zk.ARCH_TOP)), col("paint"),
               part="cargo", group="cargo", role="form")
        outside = ((lo[1], zk.AXLES["rear"] - zk.ARCH_HALF_LENGTH),
                   (zk.AXLES["rear"] + zk.ARCH_HALF_LENGTH, hi[1]))
        for sx, side in SIDES:
            x = (lo[0], -zk.ARCH_INNER_X) if sx < 0 else (zk.ARCH_INNER_X, hi[0])
            for end, (y0, y1) in enumerate(outside):
                p.mass(Mass.box(f"cargo_{side}_{end}", (x[0], y0, lo[2]), (x[1], y1, zk.ARCH_TOP)),
                       col("paint"), part="cargo", group="cargo", role="form")

    for name, point in zk.REAR_LAMPS.items():
        p.port(name, point, step=D)
    # Door edges stop inside the dedicated lamp strips X +/-.75..1.
    for sx, side in SIDES:
        x = (-11 * D, -D / 2) if sx < 0 else (D / 2, 11 * D)
        door = _back_region(p, body, x, (zk.ARCH_TOP, hi[2] - 2 * D), f"rear_door_{side}")
        p.frame(door, col("trim"), part="rear_doors", group="rear_doors", role="form",
                width=D / 4, thickness=.0125)
        handle_x = (-3 * D, -2 * D) if sx < 0 else (2 * D, 3 * D)
        handle = _back_region(p, body, handle_x, (1.5, 1.5 + 3 * D), f"rear_handle_{side}")
        p.panel(handle, col("metal"), part="rear_handles", group="rear_handles", role="structure",
                thickness=.04, offset=0.)
        hinge_x = (-12 * D, -10 * D) if sx < 0 else (10 * D, 12 * D)
        for k, z in enumerate((1.375, 2.125)):
            hinge = _back_region(p, body, hinge_x, (z, z + 2 * D), f"hinge_{side}_{k}")
            p.panel(hinge, col("metal"), part="rear_hinges", group="rear_hinges", role="structure",
                    thickness=.04, offset=0.)

        for k in range(3):
            z = zk.ARCH_TOP + D + k * 4 * D
            rib = _side_region(p, body, side, (lo[1] + 2 * D, hi[1] - 2 * D),
                               (z, z + D), f"rib_{side}_{k}")
            p.panel(rib, col("paint"), part="side_ribs", group="side_ribs", role="structure", thickness=.015)
        width = .5 if params.get("service_panel", "compact") == "compact" else 1.
        center_y = zk.AXLES["rear"] - .25
        service = _side_region(p, body, side, (center_y - width / 2, center_y + width / 2),
                               (1.75, 2.25), f"service_panel_{side}")
        p.frame(service, col("trim"), part="service_panels", group="service_panels", role="structure",
                width=D / 4, thickness=.01)
    return p


def build(params: dict[str, Any]):
    import vehlib
    import voxlib as vx

    p = plan(params)
    root = vx.empty("zk_body")
    cargo = vx.MeshBuilder()
    accessories = {}
    for prim in p.prims:
        key = za.accessory_key(prim)
        mesh = (cargo if prim.group == "cargo" else
                accessories.setdefault(key, (prim.group, vx.MeshBuilder()))[1] if key else vx.MeshBuilder())
        vehlib.draw(mesh, prim, p.stage)
        if prim.group != "cargo" and not key:
            mesh.to_object(prim.name, parent=root, semantic_part=prim.group)
    cargo.to_object("cargo", parent=root, semantic_part="cargo")
    for name, (group, mesh) in accessories.items():
        mesh.to_object(name, parent=root, semantic_part=group)
    for name, point in p.ports.items():
        vx.socket(name, point, (-90., 0., 0.), parent=root, type="vehicle_lamp")
    return root
