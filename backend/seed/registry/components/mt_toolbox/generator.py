"""Tool box of the modular truck: on the left side of the frame, in front of the tandem.

The mount point is the road under the box (kit anchor `toolbox`). Stage 1 is a block; stage 2
adds a lid, stage 3 the door outline on the outer face and a bracket to the rail, stage 4 the
handle and latches, stage 5 dark metal and hinges. Pure-Python plan (builder/blockout.py);
build() renders it with vehlib."""

from __future__ import annotations

from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID
ANCHOR = "toolbox"  # the chassis socket it mounts on
X, Y, _ = tk.ANCHORS[ANCHOR]
Z = (tk.FRAME_Z[0], tk.FRAME_Z[1])


def box(name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Mass:
    return Mass.box(name, (x[0], y[0], z[0]), (x[1], y[1], z[1]))


def plan(params: dict[str, Any]) -> Plan:
    s = params["stage"]
    p = Plan(s)
    body_c = tk.finish(s, "steel_dark", "metal_dark")
    metal = tk.finish(s, "steel", "metal_steel")
    body = box("toolbox", (X - M, X + M), (Y - M, Y + M), Z)
    p.mass(body, body_c, part="toolbox", group="toolbox", asym=True)
    p.mass(box("lid", (X - M, X + M + D), (Y - M - D, Y + M + D), (Z[1], Z[1] + D)), body_c, part="toolbox",
           group="lid", role="form", asym=True)
    face = body.face("right")                                                     # the outer face, +X
    door = p.region(face.rect(D, face.width - D, D, face.height - D, "toolbox_door"))
    p.frame(door, "soot", part="toolbox", group="toolbox_door", role="structure", width=0.02, thickness=0.012,
            asym=True)
    p.mass(box("toolbox_bracket", (tk.RAIL_X[1], X - M), (Y - D, Y + D), (Z[1] - 3 * D, Z[1] - D)), body_c,
           part="toolbox", group="toolbox_bracket", role="structure", asym=True)
    lift = bo.mul(face.outward, 0.03)
    p.beam(bo.add(face.at(face.width * 0.3, face.height * 0.75), lift),
           bo.add(face.at(face.width * 0.7, face.height * 0.75), lift), 0.03, 0.03, metal, part="toolbox",
           group="toolbox_door", role="detail", name="handle", asym=True)
    for a in (face.width * 0.2, face.width * 0.8):
        p.lamp_on(face, 0.02, metal, part="toolbox", group="toolbox_door", at=(a, face.height * 0.92),
                  role="detail", name="latch", asym=True)
    for a in (face.width * 0.25, face.width * 0.75):
        p.lamp_on(face, 0.022, metal, part="toolbox", group="toolbox_door", at=(a, D / 2), role="accent",
                  name="hinge", asym=True)
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), origin=tk.ANCHORS[ANCHOR])
