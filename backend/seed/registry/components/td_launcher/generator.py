"""TD launcher: chunky box with a rows×cols grid of big launch tubes on the front (−Y) face."""

from __future__ import annotations

from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    w, h, d = params["width"], params["height"], params["depth"]
    rows, cols = params["rows"], params["cols"]
    color, tube = params["palette_color"], params["tube_color"]
    m = vx.MeshBuilder()
    m.chamfer_box((-w / 2 * 0.9, -d / 2 * 0.9, 0.0), (w / 2 * 0.9, d / 2 * 0.9, h * 0.12), "steel_dark",
                  chamfer=params["chamfer"])
    m.chamfer_box((-w / 2, -d / 2, h * 0.12), (w / 2, d / 2, h), color, chamfer=params["chamfer"], taper=0.04)
    for sx in (-1, 1):                                       # side rails for chunkier silhouette
        x = sx * (w / 2 + 0.015)
        m.box((x - 0.02, -d / 2 * 0.8, h * 0.3), (x + 0.02, d / 2 * 0.8, h * 0.45), "steel_dark")
    cell_w, cell_h = w * 0.8 / cols, (h * 0.88 - h * 0.12) * 0.9 / rows
    rt = min(cell_w, cell_h) * 0.36
    front = -d / 2
    zc0 = h * 0.12 + (h - h * 0.12) / 2
    for i in range(cols):
        for j in range(rows):
            x = (i - (cols - 1) / 2) * cell_w
            z = zc0 + (j - (rows - 1) / 2) * cell_h
            m.prism(rt * 1.28, front - 0.03, front + 0.02, "steel_dark", sides=8, center=(z, x), axis="Y")
            m.prism(rt, front - 0.036, front - 0.029, tube, sides=8, center=(z, x), axis="Y")
    body = m.to_object("launcher")
    vx.socket("muzzle", (0.0, front - 0.036, zc0), rotation_deg=(90, 0, 0), parent=body, type="surface")
    return body
