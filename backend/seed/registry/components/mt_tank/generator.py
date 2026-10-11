"""Fuel tank of the modular truck: on the left side of the frame, under the box front.

The mount point is the road under the tank (kit anchor `tank`). Stage 1–2 is a block; stage 3
a cylinder on a bracket to the rail, stage 4 two straps, stage 5 polished steel and a filler cap.
Pure-Python plan (builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID
ANCHOR = "tank"  # the chassis socket it mounts on
X, Y, _ = tk.ANCHORS[ANCHOR]
SPAN = (Y - 2 * M, Y + 2 * M)
Z = tk.FRAME_Z[0] + M                              # tank axis height


def box(name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Mass:
    return Mass.box(name, (x[0], y[0], z[0]), (x[1], y[1], z[1]))


def plan(params: dict[str, Any]) -> Plan:
    s = params["stage"]
    p = Plan(s)
    shell = tk.finish(s, "steel", "metal_steel")
    strap = tk.finish(s, "steel_dark", "metal_dark")
    p.mass(box("tank", (X - M, X + M), SPAN, (Z - M, Z + M)), shell, part="tank", group="tank", until=2, asym=True)
    p.cylinder("y", (SPAN[0] + D, SPAN[1] - D), (X, Z), M, shell, part="tank", group="tank", role="structure",
               sides=14, name="tank", asym=True)
    for y in (SPAN[0] + 4 * D, SPAN[1] - 5 * D):
        p.mass(box("tank_bracket", (tk.RAIL_X[1], X - M + D), (y, y + D), (Z - D, Z + D)), strap, part="tank",
               group="tank_brackets", role="structure", asym=True)
        p.mass(box("tank_strap", (X - M, X + M + D), (y, y + D), (Z - M - D, Z + M + D)), strap, part="tank",
               group="tank_straps", role="detail", asym=True)
    p.cylinder("z", (Z + M - D, Z + M + 1.5 * D), (X, Y), D, "metal_dark", part="tank", group="tank",
               role="accent", sides=8, name="filler_cap", asym=True)
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), origin=tk.ANCHORS[ANCHOR])
