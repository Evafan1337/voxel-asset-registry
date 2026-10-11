"""TD base plate: chamfered slab (1–2 tiers), optional path rim and orange side strips."""

from __future__ import annotations

from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    s = vx.voxel_size()
    w, h, c = params["width"] * s, params["height"], params["chamfer"]
    hw = w / 2
    color = params["palette_color"]
    dark = "stone_dark" if color == "steel_dark" else "steel_dark"
    m = vx.MeshBuilder()
    if params["tiers"] == 2:
        h1 = h * 0.55
        inset = min(0.07, w * 0.07)
        m.chamfer_box((-hw, -hw, 0.0), (hw, hw, h1), dark, chamfer=c)
        m.chamfer_box((-hw + inset, -hw + inset, h1), (hw - inset, hw - inset, h), color,
                      chamfer=max(c - inset * 0.5, 0.0), taper=0.04)
        strip_z = (h1 * 0.3, h1 * 0.7)
    else:
        m.chamfer_box((-hw, -hw, 0.0), (hw, hw, h), color, chamfer=c, taper=0.02)
        strip_z = (h * 0.3, h * 0.55)

    if params["rim"] != "none":
        rw, rh, e = max(0.05, w * 0.07), 0.06, max(c, 0.04)
        for sx in (-1, 1):                                            # rails along the path (±X edges)
            x0, x1 = (hw - rw - 0.01, hw - 0.01) if sx > 0 else (-hw + 0.01, -hw + rw + 0.01)
            m.box((x0, -hw + e, h), (x1, hw - e, h + rh), dark)
        if params["rim"] == "full":
            for sy in (-1, 1):
                y0, y1 = (hw - rw - 0.01, hw - 0.01) if sy > 0 else (-hw + 0.01, -hw + rw + 0.01)
                m.box((-hw + e + rw, y0, h), (hw - e - rw, y1, h + rh), dark)
        k = hw - e * 0.9
        for sx in (-1, 1):                                            # corner blocks
            for sy in (-1, 1):
                m.box((sx * k - rw * 0.7, sy * k - rw * 0.7, h), (sx * k + rw * 0.7, sy * k + rw * 0.7, h + rh * 1.1),
                      "signal_orange" if params["accent"] else dark)

    if params["accent"]:
        L, t = w * 0.42, 0.008
        z0, z1 = strip_z
        m.box((-L / 2, -hw - t, z0), (L / 2, -hw + 0.002, z1), "signal_orange")
        m.box((-L / 2, hw - 0.002, z0), (L / 2, hw + t, z1), "signal_orange")
        m.box((-hw - t, -L / 2, z0), (-hw + 0.002, L / 2, z1), "signal_orange")
        m.box((hw - 0.002, -L / 2, z0), (hw + t, L / 2, z1), "signal_orange")

    base = m.to_object("base")
    mid = h * 0.5
    vx.socket("support", (0.0, 0.0, h), parent=base, type="roof")
    vx.socket("front", (0.0, -hw, mid), rotation_deg=(90, 0, 0), parent=base, type="surface")
    vx.socket("side_left", (-hw, 0.0, mid), rotation_deg=(0, -90, 0), parent=base, type="surface")
    vx.socket("side_right", (hw, 0.0, mid), rotation_deg=(0, 90, 0), parent=base, type="surface")
    return base
