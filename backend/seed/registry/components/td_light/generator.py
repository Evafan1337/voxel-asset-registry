"""TD light accent: dark mount plate + bright block / strip / orb."""

from __future__ import annotations

from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    s, color, shape = params["size"], params["color"], params["shape"]
    m = vx.MeshBuilder()
    plate = 0.02
    if shape == "strip":
        L = params["length"]
        m.box((-L / 2, -s * 0.6, 0.0), (L / 2, s * 0.6, plate), "steel_dark")
        m.box((-L / 2 + 0.01, -s * 0.35, plate), (L / 2 - 0.01, s * 0.35, plate + s * 0.45), color)
    else:
        m.box((-s * 0.7, -s * 0.7, 0.0), (s * 0.7, s * 0.7, plate), "steel_dark")
        if shape == "orb":
            m.sphere((0.0, 0.0, plate + s / 2), s / 2, color, rings=4, sides=8)
        else:
            m.chamfer_box((-s / 2, -s / 2, plate), (s / 2, s / 2, plate + s), color, chamfer=s * 0.2)
    return m.to_object("light")
