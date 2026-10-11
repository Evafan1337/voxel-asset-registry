"""Cargo box of the modular truck: a framed van body on a subframe.

The mount point is the road under the box centre (kit anchor `box`). Stage 1 is the box mass;
stage 2 adds the subframe down to the rails; from stage 3 the frame (corner posts, rails) runs on
the stage-1 edges and the panels sit one DETAIL inside it, so no part lies flush with a face of
another colour. Stage 4 adds panel seams, the red/white reflective strips, marker lights and the
rear doors with hinges; stage 5 chrome corner caps and lock bars. Pure-Python plan
(builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID
ANCHOR = "box"  # the chassis socket it mounts on
MEMBER = 2 * D                                     # posts and rails


def box(name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Mass:
    return Mass.box(name, (x[0], y[0], z[0]), (x[1], y[1], z[1]))


def plan(params: dict[str, Any]) -> Plan:
    s, color = params["stage"], params["color"]
    p = Plan(s)
    trim = tk.finish(s, "steel", "metal_steel")
    W, (y0, y1), (z0, z1) = tk.BOX_W, tk.BOX_Y, (tk.BOX_FLOOR, tk.BOX_TOP)

    body = box("body", (-W, W), tk.BOX_Y, (z0, z1))
    p.mass(body, color, part="box", until=2)
    p.mass(box("subframe", (-tk.FRAME_W, tk.FRAME_W), (y0 + MEMBER, y1 - MEMBER), (tk.FRAME_Z[1], z0)),
           tk.finish(s, "steel_dark", "metal_dark"), part="box", group="subframe", role="form")
    panels = box("panels", (-W + D, W - D), (y0 + D, y1 - D), (z0 + D, z1 - D))
    p.mass(panels, color, part="box", group="body", role="structure")
    ends = {"front": (y0, y0 + MEMBER), "back": (y1 - MEMBER, y1)}
    levels = {"bottom": (z0, z0 + MEMBER), "top": (z1 - MEMBER, z1)}
    for sx, name in ((-1, "right"), (1, "left")):
        edge = tk.mirror(sx, W - MEMBER, W)
        for end, ys in ends.items():
            p.mass(box(f"post_{end}_{name}", edge, ys, (z0, z1)), trim, part="box", group="body", role="structure")
        for level, zs in levels.items():
            p.mass(box(f"rail_{level}_{name}", edge, tk.BOX_Y, zs), trim, part="box", group="body", role="structure")
    for end, ys in ends.items():
        for level, zs in levels.items():
            p.mass(box(f"rail_{level}_{end}", (-W, W), ys, zs), trim, part="box", group="body", role="structure")

    # ------------------------------------------------------------------ sides: seams, reflective strip, markers
    outer = {name: body.face(name) for name in ("left", "right")}
    for sx, name in ((-1, "right"), (1, "left")):
        face = panels.face(name)
        lo, hi = MEMBER - D, face.width - (MEMBER - D)                           # open span between the posts
        for k in range(1, 6):
            a = lo + (hi - lo) * k / 6
            seam = p.region(face.rect(a - D / 4, a + D / 4, D, face.height - D, f"seam_{name}_{k}"))
            p.panel(seam, tk.finish(s, "steel_dark", "metal_dark"), part="box", group="seams", role="detail",
                    thickness=D / 4)
        rail_face = outer[name]                                                   # the bottom rail's outer face
        strip = p.region(rail_face.rect(3 * D, rail_face.width - 3 * D, D / 2, MEMBER - D / 2, f"strip_{name}"))
        for k, dash in enumerate(strip.split_a(12, 2 * D, f"strip_{name}")):
            p.panel(dash, "reflector_red" if k % 2 == 0 else "reflector_white", part="box", group="strips",
                    role="detail", thickness=0.012)
        for a in (MEMBER / 2, rail_face.width - MEMBER / 2):
            p.lamp_on(rail_face, D / 2, "lamp_amber", part="box", group="markers", at=(a, rail_face.height - M),
                      role="detail", name="side_marker")
    for end, lamp in (("front", "lamp_amber"), ("back", "lamp_red")):            # clearance lights on the posts
        face = body.face(end)
        for a in (MEMBER / 2, face.width - MEMBER / 2):
            p.lamp_on(face, D / 2, lamp, part="box", group="markers", at=(a, face.height - 5 * D), role="detail",
                      name="clearance_light")

    # ------------------------------------------------------------------ rear doors
    back = panels.face("back")
    seam = p.region(back.rect(back.width / 2 - D / 4, back.width / 2 + D / 4, D, back.height - D, "door_seam"))
    p.panel(seam, tk.finish(s, "steel_dark", "metal_dark"), part="box", group="rear_doors", role="detail",
            thickness=0.02)
    for a0 in (D, back.width - 3 * D):
        for b0 in (3 * D, back.height / 2 - D, back.height - 5 * D):
            hinge = p.region(back.rect(a0, a0 + 2 * D, b0, b0 + 2 * D, f"hinge_{a0:.2f}_{b0:.2f}"))
            p.panel(hinge, trim, part="box", group="rear_doors", role="detail", thickness=0.04)
    lift = bo.mul(back.outward, 0.035)
    for x in (-10 * D, -5 * D, 5 * D, 10 * D):                                    # lock bars, mirrored pairs
        a = back.local((x, 0.0, z0))[0]
        p.beam(bo.add(back.at(a, 3 * D), lift), bo.add(back.at(a, back.height - 3 * D), lift), 0.04, 0.04,
               "metal_steel", part="box", group="rear_doors", role="accent", name="lock_bar")
    for sx in (-1, 1):                                                            # chrome caps on the top corners
        for yc in (y0, y1):
            xr = tk.mirror(sx, W - MEMBER - D, W + D)
            yr = (yc - D, yc + MEMBER + D) if yc == y0 else (yc - MEMBER - D, yc + D)
            p.mass(box("corner_cap", xr, yr, (z1 - MEMBER - D, z1 + D)), "metal_steel", part="box",
                   group="corner_caps", role="accent")
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), origin=tk.ANCHORS[ANCHOR])
