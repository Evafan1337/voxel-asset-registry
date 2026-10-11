"""Zuk's common anchor frame, integrated bumpers and chassis-supported steps.

The source block remains the same envelope. Refined rails retreat inside the
front wheel's full steering/bump sweep; no cosmetic braces or extra hardware.
"""
from __future__ import annotations

from typing import Any

import blockout as bo
import zuklib as zk
from blockout import Mass, Plan

D = bo.DETAIL_GRID


def plan(params: dict[str, Any]) -> Plan:
    stage = int(params.get("stage", 3))
    p = Plan(stage)
    col = lambda role: zk.color(stage, role, params.get("paint", "paint_gray"), params.get("finish", True))
    profile = zk.layout(params)
    inset = params.get("wheel_fit", "legacy") == "inset"
    for name, point in zk.ANCHORS.items():
        p.port(name, point)
    frame = (Mass.box("frame", (-.5, zk.CHASSIS_LO[1], zk.CHASSIS_LO[2]),
                      (.5, zk.CHASSIS_HI[1], zk.CHASSIS_HI[2])) if inset else
             Mass.box("frame", zk.CHASSIS_LO, zk.CHASSIS_HI))
    p.mass(frame, col("metal"), part="chassis", group="chassis", until=1)
    lo, hi = frame.bounds
    for sx, side in ((-1, "left"), (1, "right")):
        x = (-profile.rail_outer, -profile.rail_inner) if sx < 0 else (profile.rail_inner, profile.rail_outer)
        rail = Mass.box(f"rail_{side}", (x[0], lo[1] if inset else lo[1] + D, lo[2]),
                        (x[1], hi[1] if inset else hi[1] - D, hi[2]))
        p.mass(rail, col("metal"), part="chassis", group="chassis", role="form")
        # A short tread is located behind the front sweep, directly on the rail.
        step_y = (zk.CAB_HI[1] - 3 * D, zk.CAB_HI[1])
        step_x = (-1., x[0]) if sx < 0 else (x[1], 1.)
        p.mass(Mass.box(f"step_{side}", (step_x[0], step_y[0], lo[2] + D),
                        (step_x[1], step_y[1], hi[2] - D)), col("metal"),
               part="steps", group="steps", role="structure")
    for name, y in (("front", (lo[1] + D, lo[1] + 2 * D)),
                    ("middle", (-D, D)), ("rear", (hi[1] - 2 * D, hi[1] - D))):
        cross = Mass.box(f"cross_{name}", (lo[0], y[0], lo[2]), (hi[0], y[1], hi[2]))
        p.mass(cross, col("metal"), part="chassis", group="chassis", role="form")
    bumpers = (("front_bumper", (lo[1] - D, lo[1])), ("rear_bumper", (hi[1], hi[1] + D))) if inset else (
               ("front_bumper", (lo[1], lo[1] + D)), ("rear_bumper", (hi[1] - D, hi[1])))
    for name, y in bumpers:
        p.mass(Mass.box(name, (-1., y[0], lo[2]), (1., y[1], hi[2])), col("metal"),
               part=name, group=name, role="form")
    return p


def build(params: dict[str, Any]):
    import vehlib
    import voxlib as vx

    p = plan(params)
    root = vx.empty("zk_chassis")
    frame = vx.MeshBuilder()
    for prim in p.prims:
        mesh = frame if prim.group == "chassis" else vx.MeshBuilder()
        vehlib.draw(mesh, prim, p.stage)
        if prim.group != "chassis":
            mesh.to_object(prim.name, parent=root, semantic_part=prim.group)
    frame.to_object("chassis", parent=root, semantic_part="chassis")
    for name, point in p.ports.items():
        vx.socket(name, point, parent=root, type="generic")
    return root
