"""Chassis of the modular truck: the frame every other block of the kit docks on.

Stage 1 is one frame mass; stage 2 refines it into two rails and leaf springs over the three
axles; stage 3 adds cross members and the rear bumper with tail lights, stage 4 mud flaps behind
the tandem, stage 5 a reflector strip and dark-metal finish. The sockets are the kit anchors of
builder/trucklib.py on the road under each mount point: cab, box, three axles, exhaust, tank,
tool box. Pure-Python plan (builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID


def box(name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Mass:
    return Mass.box(name, (x[0], y[0], z[0]), (x[1], y[1], z[1]))


def plan(params: dict[str, Any]) -> Plan:
    s = params["stage"]
    p = Plan(s)
    rail = tk.finish(s, "soot", "metal_dark")
    trim = tk.finish(s, "steel_dark", "metal_dark")
    for name, point in tk.ANCHORS.items():
        p.port(name, point)

    frame = box("frame", (-tk.FRAME_W, tk.FRAME_W), tk.FRAME_Y, tk.FRAME_Z)
    p.mass(frame, rail, part="chassis", group="chassis", until=1)
    rail_y = (tk.FRAME_Y[0] + D, tk.FRAME_Y[1] - D)
    top = tk.FRAME_Z[1]
    for sx, name in ((-1, "right"), (1, "left")):
        p.mass(box(f"rail_{name}", tk.mirror(sx, *tk.RAIL_X), rail_y, (top - M, top)), rail, part="chassis",
               group="chassis", role="form")
        for axle, y in tk.AXLES.items():                                          # leaf springs over the axles
            p.mass(box(f"spring_{axle}_{name}", tk.mirror(sx, *tk.RAIL_X), (y - 4 * D, y + 4 * D),
                       (tk.WHEEL_R + D, top - M)), trim, part="chassis", group="chassis", role="form")
    for k in range(6):
        y = bo.lerp((0.0, rail_y[0] + 2 * D, 0.0), (0.0, rail_y[1] - 2 * D, 0.0), k / 5)[1]
        p.mass(box(f"cross_member_{k}", (-tk.RAIL_X[0], tk.RAIL_X[0]), (bo.snap(y, D) - D, bo.snap(y, D) + D),
                   (top - M, top - 2 * D)), rail, part="chassis", group="chassis", role="structure")

    # rear bumper with tail lights, mud flaps behind the tandem
    bumper = box("rear_bumper", (-4 * M, 4 * M), (tk.FRAME_Y[1] - D, tk.FRAME_Y[1] + 2 * D),
                 (tk.FRAME_Z[0], tk.FRAME_Z[0] + M))
    p.mass(bumper, trim, part="chassis", group="rear_bumper", role="structure")
    back = bumper.face("back")
    for a in (2 * D, back.width - 2 * D):
        p.lamp_on(back, D, "lamp_red", part="chassis", group="rear_bumper", at=(a, back.height / 2),
                  role="structure", name="tail_light")
    strip = p.region(back.rect(5 * D, back.width - 5 * D, back.height / 2 - D / 2, back.height / 2 + D / 2,
                               "reflector_strip"))
    for k, part in enumerate(strip.split_a(6, D / 2, "reflector")):
        p.panel(part, "reflector_red" if k % 2 == 0 else "reflector_white", part="chassis", group="rear_bumper",
                role="accent", thickness=0.01)
    y_flap = tk.AXLES["rear_2"] + tk.WHEEL_R + D
    for sx, name in ((-1, "right"), (1, "left")):
        p.mass(box(f"mud_flap_{name}", tk.mirror(sx, tk.RAIL_X[1], tk.WHEEL_X + 3 * D), (y_flap, y_flap + D),
                   (tk.WHEEL_R / 2, top)), "rubber", part="chassis", group="mud_flaps", role="detail")
    return p


SOCKETS = {name: ("generic", (0.0, 0.0, 0.0)) for name in tk.ANCHORS}


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), sockets=SOCKETS)
