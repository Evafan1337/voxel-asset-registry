"""TD sensor: housing + oversized glowing eye on the far (+Z) face."""

from __future__ import annotations

import math
from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    s, d = params["size"], params["depth"]
    e = s * params["eye"]
    color, eye = params["palette_color"], params["eye_color"]
    m = vx.MeshBuilder()
    if params["shape"] == "round":
        m.prism(s / 2, 0.0, d, color, sides=10, phase=math.pi / 10)
        m.prism(e / 2 * 1.25, d, d + 0.012, "soot", sides=10, phase=math.pi / 10)
        m.prism(e / 2, d + 0.012, d + 0.03, eye, sides=10, phase=math.pi / 10)
    else:
        m.chamfer_box((-s / 2, -s / 2, 0.0), (s / 2, s / 2, d), color, chamfer=s * 0.15)
        m.chamfer_box((-e / 2 * 1.2, -e / 2 * 1.2, d), (e / 2 * 1.2, e / 2 * 1.2, d + 0.012), "soot", chamfer=e * 0.15)
        m.chamfer_box((-e / 2, -e / 2, d + 0.012), (e / 2, e / 2, d + 0.03), eye, chamfer=e * 0.12)
    return m.to_object("sensor")
