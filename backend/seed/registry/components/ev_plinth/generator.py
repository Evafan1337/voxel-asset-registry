"""Display plinth for evolution showcases: a low slab, stage pips on the front edge and an arrow
chevron on the floor to the next plinth (+X). Socket `top` turns a vehicle to face +X."""

from __future__ import annotations

from typing import Any

import mechlib
import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    w, d, h = params["width"], params["depth"], params["height"]
    color, accent = params["color"], params["accent"]
    m = vx.MeshBuilder()
    m.box((-w / 2, -d / 2, 0.0), (w / 2, d / 2, h), color)
    if params["edge"]:
        m.box((-w / 2, -d / 2 - 0.02, h - 0.04), (w / 2, -d / 2 + 0.06, h + 0.01), accent)     # front lip
    root = m.to_object("plinth", semantic_part="plinth")

    marks = vx.MeshBuilder()
    n = params["pips"]
    for i in range(n):                                                                  # stage pips
        x = (i - (n - 1) / 2) * 0.32
        marks.box((x - 0.1, -d / 2 + 0.14, h), (x + 0.1, -d / 2 + 0.34, h + 0.03), accent)
    if params["arrow"]:
        x0, L = w / 2 + 0.2, max(0.4, params["gap"] - 0.4)
        mechlib.convex_prism(marks, [(x0, -0.28), (x0 + L * 0.55, -0.28), (x0 + L * 0.55, 0.28), (x0, 0.28)],
                             0.0, 0.03, accent)
        mechlib.convex_prism(marks, [(x0 + L * 0.55, -0.5), (x0 + L, 0.0), (x0 + L * 0.55, 0.5)], 0.0, 0.03, accent)
    if marks.verts:
        marks.to_object("marks", parent=root, semantic_part="marks")

    vx.socket("top", (0.0, 0.0, h), rotation_deg=(0, 0, 90), parent=root, type="roof")     # vehicles face +X
    vx.socket("center", (0.0, 0.0, h), parent=root, type="ground")
    vx.socket("left_end", (-w / 2, 0.0, h), parent=root, type="ground")                   # a row starts here
    vx.socket("next", (w / 2, 0.0, 0.0), parent=root, type="ground")                      # the next plinth
    return root
