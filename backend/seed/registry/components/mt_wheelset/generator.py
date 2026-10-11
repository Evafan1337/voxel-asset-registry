"""Wheel set of the modular truck: an axle with two wheels, or twin wheels at the back (`dual`).

The mount point is the road under the axle centre; the axle sits at z = WHEEL_R. The tyre is one
mass at every stage that only gets rounder — an octagon standing on a flat (stages 1–2), 12 sides
(3–4), 16 sides (5). Stage 2 adds the square hub of the reference, stage 3 a rim, a hub cap and
the differential of a twin axle, stage 4 lug nuts, stage 5 the real-time materials (steel rim,
chrome cap). Pure-Python plan (builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

import math
from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID
R, W = tk.WHEEL_R, tk.WHEEL_W


def plan(params: dict[str, Any]) -> Plan:
    s, dual = params["stage"], params["dual"]
    p = Plan(s)
    rim, cap = tk.finish(s, "steel", "metal_steel"), tk.finish(s, "steel_dark", "metal_steel")
    sides = {1: 8, 2: 8, 3: 12, 4: 12}.get(s, 16)
    p.cylinder("x", (-tk.WHEEL_X, tk.WHEEL_X), (0.0, R), D, tk.finish(s, "steel_dark", "metal_dark"), part="wheels",
               group="axle", role="mass", sides=8, name="axle")
    centres = [tk.WHEEL_X] + ([tk.WHEEL_X - W - D] if dual else [])
    for sx, name in ((-1, "right"), (1, "left")):
        for k, cx in enumerate(centres):
            x0, x1 = tk.mirror(sx, cx - W / 2, cx + W / 2)
            p.cylinder("x", (x0, x1), (0.0, R), R, "rubber", part="wheels", group="wheels", role="mass",
                       sides=sides, flat=True, name=f"tyre_{name}_{k}")
        face = sx * (tk.WHEEL_X + W / 2)                                          # outer face of the outer wheel
        lo, hi = sorted((face - sx * D / 2, face + sx * D / 2))
        p.mass(Mass.box(f"hub_{name}", (lo, -2 * D, R - 2 * D), (hi, 2 * D, R + 2 * D)), rim, part="wheels",
               group="hubs", role="form", until=2)                                # the square hub of the reference
        lo, hi = sorted((face - sx * D / 4, face + sx * D / 4))
        p.cylinder("x", (lo, hi), (0.0, R), 0.62 * R, rim, part="wheels", group="rims", role="structure",
                   sides=sides, name=f"rim_{name}")
        lo, hi = sorted((face, face + sx * D * 0.75))
        p.cylinder("x", (lo, hi), (0.0, R), 0.24 * R, cap, part="wheels", group="rims", role="structure", sides=8,
                   name=f"hub_cap_{name}")
        for i in range(6):                                                        # lug nuts on a bolt circle
            a = 2 * math.pi * (i + 0.5) / 6
            c = (sx * (tk.WHEEL_X + W / 2 + D / 2), 0.38 * R * math.cos(a), R + 0.38 * R * math.sin(a))
            p.lamp(c, 0.022, "metal_dark" if s >= 5 else "steel_dark", part="wheels", group="nuts", role="detail",
                   name="lug_nut")
    if dual:                                                                      # differential of a driven axle
        p.mass(Mass.box("differential", (-3 * D, -3 * D, R - 3 * D), (3 * D, 3 * D, R + 3 * D)),
               tk.finish(s, "steel_dark", "metal_dark"), part="wheels", group="axle", role="structure")
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params))
