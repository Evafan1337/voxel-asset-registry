"""TD ring: horizontal rim around the mount axis, optional hub + spokes."""

from __future__ import annotations

import math
from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    R, tube, h, n = params["radius"], params["tube"], params["height"], params["segments"]
    m = vx.MeshBuilder()
    m.ring(R - tube, R, 0.0, h, params["palette_color"], sides=n, phase=math.pi / n)
    if params["spokes"]:
        hub = params["hub_radius"]
        m.prism(hub, 0.0, h * 1.6, "steel_dark", sides=8, phase=math.pi / 8)          # hub collar on the axis
        for i in range(params["spokes"]):
            a = 2 * math.pi * i / params["spokes"] + math.pi / 2
            p0 = (hub * 0.8 * math.cos(a), hub * 0.8 * math.sin(a), h / 2)
            p1 = ((R - tube * 0.5) * math.cos(a), (R - tube * 0.5) * math.sin(a), h / 2)
            m.strut(p0, p1, min(0.04, h * 0.7), "steel_dark")
    return m.to_object("ring")
