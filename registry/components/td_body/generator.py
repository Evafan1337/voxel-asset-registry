"""TD hull: chamfered box (turret housing / walker hull) or faceted sphere (drone), lifted by `lift`."""

from __future__ import annotations

import math
from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    w, d, h, lift = params["width"], params["depth"], params["height"], params["lift"]
    c, taper = params["chamfer"], params["taper"]
    color, trim = params["palette_color"], params["trim_color"]
    m = vx.MeshBuilder()
    z0, z1 = lift, lift + h

    if params["shape"] == "round":
        r = (w + d) / 4
        zc = z0 + h / 2
        m.sphere((0.0, 0.0, zc), r, color, rings=6, sides=10, squash=h / (2 * r))
        m.prism(r * 1.04, zc - h * 0.07, zc + h * 0.07, trim, sides=10)   # equator band, aligned with the sphere facets
        front_y, side_x, mid_z, sensor_z = -r * 0.98, r * 0.98, zc, zc
        leg_x, leg_y = r * 0.55, r * 0.55
    else:
        band = h * 0.22
        k = 0.92
        m.chamfer_box((-w / 2 * k, -d / 2 * k, z0), (w / 2 * k, d / 2 * k, z0 + band), trim, chamfer=c * k)
        m.chamfer_box((-w / 2, -d / 2, z0 + band), (w / 2, d / 2, z1), color, chamfer=c, taper=taper)

        def face(z: float) -> float:                     # front-face offset at height z (tapered shell)
            f = (z - z0 - band) / max(h - band, 1e-6)
            return 1 - taper * min(max(f, 0.0), 1.0)

        mid_z = z0 + band + (h - band) * 0.45
        sensor_z = z0 + band + (h - band) * 0.62
        front_y, side_x = -d / 2 * face(mid_z), w / 2 * face(mid_z)
        leg_x, leg_y = w / 2 * 0.72, d / 2 * 0.72
    body = m.to_object("hull")

    sensor_y = front_y if params["shape"] == "round" else -d / 2 * (1 - taper * 0.62)
    vx.socket("weapon", (0.0, front_y, mid_z), rotation_deg=(90, 0, 0), parent=body, type="surface")
    vx.socket("sensor", (0.0, sensor_y, sensor_z), rotation_deg=(90, 0, 0), parent=body, type="surface")
    vx.socket("top", (0.0, 0.0, z1), parent=body, type="roof")
    vx.socket("bottom", (0.0, 0.0, z0), rotation_deg=(180, 0, 0), parent=body, type="surface")
    vx.socket("side_left", (-side_x, 0.0, mid_z), rotation_deg=(0, -90, 0), parent=body, type="surface")
    vx.socket("side_right", (side_x, 0.0, mid_z), rotation_deg=(0, 90, 0), parent=body, type="surface")
    # legs: socket +Z points down to the foot, +X points outward (knee direction)
    for name, sx, sy in (("leg_fl", -1, -1), ("leg_fr", 1, -1), ("leg_bl", -1, 1), ("leg_br", 1, 1)):
        yaw = math.degrees(math.atan2(sy, sx))
        vx.socket(name, (sx * leg_x, sy * leg_y, z0), rotation_deg=(180, 0, yaw), parent=body, type="leg")
    return body
