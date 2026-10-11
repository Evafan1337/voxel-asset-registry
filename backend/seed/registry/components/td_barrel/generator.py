"""TD barrel: single or clustered barrels along +Z, optional taper (spike), collar and muzzle rings."""

from __future__ import annotations

import math
from typing import Any

import voxlib as vx


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    L, r, n, taper = params["barrel_length"], params["barrel_radius"], params["count"], params["taper"]
    color = params["palette_color"]
    m = vx.MeshBuilder()
    start = 0.0
    if params["collar"]:
        cl = min(0.12, L * 0.25)
        m.prism(r * (2.5 if n > 1 else 1.6), 0.0, cl, "steel_dark", sides=8, phase=math.pi / 8)
        start = cl * 0.5
    spread = r * 1.25 if n > 1 else 0.0
    muzzle_len = min(0.06, L * 0.12) if params["muzzle"] else 0.0
    for i in range(n):
        a = 2 * math.pi * i / n + math.pi / 2
        center = (spread * math.cos(a), spread * math.sin(a))
        segments = 1 if taper < 0.05 else 3
        for k in range(segments):
            za = start + (L - muzzle_len - start) * k / segments
            zb = start + (L - muzzle_len - start) * (k + 1) / segments
            rk = r * (1 - taper * (k + 0.5) / segments)
            m.prism(rk, za, zb + (0.001 if k < segments - 1 else 0.0), color, sides=8, center=center)
        if muzzle_len:
            m.prism(r * (1 - taper) * 1.3, L - muzzle_len, L, "steel_dark", sides=8, center=center)
    barrel = m.to_object("barrel")
    vx.socket("muzzle", (0.0, 0.0, L), parent=barrel, type="surface")
    return barrel
