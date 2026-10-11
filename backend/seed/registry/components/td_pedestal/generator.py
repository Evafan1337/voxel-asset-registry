"""TD pedestal / mast / pillar: foot skirt, tapered column, cap plate; top + collar sockets."""

from __future__ import annotations

from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    w, H, taper = params["width"], params["height"], params["taper"]
    octagon = params["shape"] == "octagon"
    color = params["palette_color"]
    dark = "stone_dark" if color == "steel_dark" else "steel_dark"
    hw = w / 2
    m = vx.MeshBuilder()
    z = 0.0
    if params["foot"]:
        fh, fw = min(0.1, H * 0.2), hw * 1.45
        m.chamfer_box((-fw, -fw, 0.0), (fw, fw, fh), dark, chamfer=fw * (0.42 if octagon else 0.08), taper=0.15)
        z = fh
    cap_h = min(0.06, H * 0.12)
    m.chamfer_box((-hw, -hw, z), (hw, hw, H - cap_h), color, chamfer=hw * (0.42 if octagon else 0.06), taper=taper)
    top_hw = hw * (1 - taper) * 1.18
    m.chamfer_box((-top_hw, -top_hw, H - cap_h), (top_hw, top_hw, H), dark,
                  chamfer=top_hw * (0.42 if octagon else 0.06))
    if params["accent"]:
        z0, z1 = H * 0.72, H * 0.8
        frac = (z0 - z) / max(H - cap_h - z, 1e-6)
        bw = hw * (1 - taper * frac) + 0.01
        m.chamfer_box((-bw, -bw, z0), (bw, bw, z1), "signal_orange", chamfer=bw * (0.42 if octagon else 0.06))
    body = m.to_object("pedestal")
    vx.socket("top", (0.0, 0.0, H), parent=body, type="roof")
    vx.socket("collar", (0.0, 0.0, H * params["collar_at"]), parent=body, type="roof")
    return body
