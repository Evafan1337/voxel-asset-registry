"""Exhaust stack of the modular truck: a vertical pipe behind the cab on the left side.

The mount point is the road under the stack (kit anchor `exhaust`). Stage 1 is one column mass
from the frame to above the cab roof; stage 2 refines it into a pipe with a top bent backwards, a
bracket to the cab back and a down pipe into the frame; stage 3 adds the heat shield, stage 4
clamps at its ends, stage 5 chrome and the perforation of the shield. Pure-Python plan
(builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

import math
from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID
ANCHOR = "exhaust"  # the chassis socket it mounts on
X, Y, _ = tk.ANCHORS[ANCHOR]
Z = (tk.FRAME_Z[1] - M, 12 * M)                    # from the frame up past the cab roof
PIPE, SHIELD = 1.5 * D, 2.5 * D                    # radii
SHIELD_Z = (6 * M, 10 * M)


def plan(params: dict[str, Any]) -> Plan:
    s = params["stage"]
    p = Plan(s)
    pipe = tk.finish(s, "steel", "metal_steel")
    clamp = tk.finish(s, "steel_dark", "metal_dark")
    column = Mass.box("column", (X - M / 2, Y - M / 2, Z[0]), (X + M / 2, Y + M / 2, Z[1]))
    p.mass(column, pipe, part="exhaust", group="exhaust", until=1, asym=True)
    top = Z[1] - 4 * D
    p.cylinder("z", (Z[0] + D, top), (X, Y), PIPE, pipe, part="exhaust", group="exhaust", role="form", sides=10,
               name="pipe", asym=True)
    bend = [(X, Y, top - D), (X, Y + D, top + 2 * D), (X, Y + 2 * D, Z[1])]       # the top bent backwards
    for a, b in zip(bend, bend[1:]):
        p.beam(a, b, 2 * PIPE, 2 * PIPE, pipe, part="exhaust", group="exhaust", role="form", name="bend", asym=True)
    p.beam((X, Y - PIPE, 8 * M), (X, tk.CAB_Y[1], 8 * M), 0.05, 0.05, clamp, part="exhaust", group="brackets",
           role="form", name="cab_bracket", asym=True)
    p.beam((X, Y, Z[0] + D), (tk.RAIL_X[1], Y, Z[0] + D), 2 * PIPE, 2 * PIPE, pipe, part="exhaust",
           group="brackets", role="form", name="down_pipe", asym=True)
    p.cylinder("z", SHIELD_Z, (X, Y), SHIELD, tk.finish(s, "steel_dark", "metal_steel"), part="exhaust",
               group="exhaust", role="structure", sides=10, name="heat_shield", asym=True)
    for z in SHIELD_Z:
        p.cylinder("z", (z - D / 2, z + D / 2), (X, Y), SHIELD + D / 2, clamp, part="exhaust", group="clamps",
                   role="detail", sides=10, name="clamp", asym=True)
    for row in range(6):                                                          # perforation of the shield
        z = SHIELD_Z[0] + (SHIELD_Z[1] - SHIELD_Z[0]) * (row + 0.5) / 6
        for deg in (-75, -40, -5, 30):                                            # the side facing out and forward
            a = math.radians(deg + (17 if row % 2 else 0))
            c = (X + SHIELD * math.cos(a), Y + SHIELD * math.sin(a), z)
            p.lamp(c, 0.016, "soot", part="exhaust", group="perforation", role="accent", name="hole", asym=True)
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), origin=tk.ANCHORS[ANCHOR])
