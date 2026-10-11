"""TD panel: chamfered plate with optional dark plinth and orange face strip; end/top sockets."""

from __future__ import annotations

from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    w, h, t, c = params["width"], params["height"], params["panel_thickness"], params["chamfer"]
    color = params["palette_color"]
    m = vx.MeshBuilder()
    z = 0.0
    if params["frame"]:
        z = h * 0.18
        m.chamfer_box((-w / 2, -t / 2, 0.0), (w / 2, t / 2, z), "steel_dark", chamfer=c)
    k = 0.92 if params["frame"] else 1.0
    m.chamfer_box((-w / 2 + 0.005, -t / 2 * k, z), (w / 2 - 0.005, t / 2 * k, h), color, chamfer=c, taper=0.04)
    if params["accent"]:
        m.box((-w * 0.38, -t / 2 * k - 0.01, h * 0.52), (w * 0.38, -t / 2 * k + 0.004, h * 0.64), "signal_orange")
    panel = m.to_object("panel")
    vx.socket("top", (0.0, 0.0, h), parent=panel, type="roof")
    vx.socket("side_left", (-w / 2, 0.0, 0.0), parent=panel, type="roof")
    vx.socket("side_right", (w / 2, 0.0, 0.0), parent=panel, type="roof")
    return panel
