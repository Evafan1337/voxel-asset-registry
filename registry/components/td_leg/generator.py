"""TD leg: hip joint → knee (out along +X) → foot pad at z = leg_length (local +Z = toward the foot)."""

from __future__ import annotations

from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    L, t, k, f = params["leg_length"], params["thickness"], params["knee_out"], params["foot_size"]
    color = params["palette_color"]
    m = vx.MeshBuilder()
    hip = t * 1.25
    m.chamfer_box((-hip / 2, -hip / 2, 0.0), (hip / 2, hip / 2, hip), "steel_dark", chamfer=hip * 0.2)
    knee_z = L * 0.3
    knee = (k, 0.0, knee_z)
    foot_h = min(f * 0.45, L * 0.2)
    foot_x = k + L * 0.1
    m.strut((0.0, 0.0, hip * 0.5), knee, t * 1.1, color)                  # thigh: out and slightly down
    j = t * 0.75
    m.chamfer_box((k - j, -j, knee_z - j), (k + j, j, knee_z + j), "steel_dark", chamfer=j * 0.3)
    m.strut(knee, (foot_x, 0.0, L - foot_h), t * 0.9, color)               # shin: down to the foot
    m.chamfer_box((foot_x - f * 0.75, -f * 0.65, L - foot_h), (foot_x + f * 0.75, f * 0.65, L), "steel_dark",
                  chamfer=f * 0.25)
    return m.to_object("leg")
