"""Cab of the modular truck: bonnet, cab, bumper, glazing, grille, lights, fenders, mirrors, steps.

The mount point is the road under the cab front (kit anchor `cab`). Stage 1 is two masses — cab
and bonnet; stage 2 splits the cab into a tub and a greenhouse with a raked windscreen, tapers the
bonnet and adds the bumper and mirrors on arms; stage 3 puts tinted glass, doors, the grille,
yellow headlights and fenders into regions and ports; stage 4 frames, grille slats, roof and side
markers, steps, handles, upper mirror arms; stage 5 chrome (bumper, grille surround), a plate and
turn signals. Pure-Python plan (builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

from typing import Any

import blockout as bo
import trucklib as tk
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID
ANCHOR = "cab"  # the chassis socket it mounts on
TUB_TOP = 7 * M                                   # tub / greenhouse split
SCREEN_RAKE = 2 * D                               # the windscreen top sits this far back


def box(name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Mass:
    return Mass.box(name, (x[0], y[0], z[0]), (x[1], y[1], z[1]))


def plan(params: dict[str, Any]) -> Plan:
    s, paint = params["stage"], params["paint"]
    p = Plan(s)
    chrome = tk.finish(s, "paint_gray", "metal_steel")
    dark = tk.finish(s, "soot", "plastic")
    W, (y0, y1), top = tk.CAB_W, tk.CAB_Y, tk.CAB_TOP

    # ------------------------------------------------------------------ cab: block → tub + greenhouse wedge
    cab = box("cab", (-W, W), tk.CAB_Y, (tk.CAB_FLOOR, top))
    p.mass(cab, paint, part="cab", until=1)
    tub = box("tub", (-W, W), tk.CAB_Y, (tk.CAB_FLOOR, TUB_TOP))
    house = Mass.wedge("greenhouse", (-W, W, y0, y1), (-W + D, W - D, y0 + SCREEN_RAKE, y1), TUB_TOP, top)
    p.mass(tub, paint, part="cab", group="cab", role="form")
    p.mass(house, paint, part="cab", group="cab", role="form")

    front = house.face("front")
    shield = front.span(2 * D, D, front.height - 2 * D, "windscreen")
    for pane in shield.split_a(2, 2 * D, "windscreen"):                    # two-piece windscreen
        p.region(pane)
        p.panel(pane, "glass_tinted", part="cab", group="cab", role="structure")
        p.frame(pane, dark, part="cab", group="cab_frames", role="detail", width=0.03)
    for sx, name in ((-1, "right"), (1, "left")):
        side, tub_side = house.face(name), tub.face(name)
        band = side.span(2 * D, 2 * D, side.height - 2 * D, f"side_{name}")
        window = p.region(band.sub(0.0, 0.7, 0.0, 1.0, f"window_{name}"))
        p.panel(window, "glass_tinted", part="cab", group="cab", role="structure")
        p.frame(window, dark, part="cab", group="cab_frames", role="detail", width=0.03)
        a0, a1 = tub_side.local(window.corners[0])[0], tub_side.local(window.corners[1])[0]
        door = p.region(tub_side.rect(a0, a1, D, tub_side.height - D, f"door_{name}"))
        p.frame(door, dark, part="cab", group="cab_frames", role="structure", width=0.02, thickness=0.015)
        p.panel(door.sub(0.75, 0.92, 0.6, 0.72, f"handle_{name}"), chrome, part="cab", group="cab_frames",
                role="detail", thickness=0.03)
        p.lamp_on(tub_side, D / 2, "lamp_amber", part="cab", group="markers", at=(2 * D, tub_side.height / 2),
                  name="side_marker")

        # mirror: a head beside the A-pillar on an arm from the tub corner, a second arm from the greenhouse
        mount = p.port(f"mirror_{name}", tub_side.at(M, tub_side.height))
        head = box(f"mirror_{name}", tk.mirror(sx, W + D, W + 3 * D), (mount[1] - 2 * D, mount[1]),
                   (mount[2] + D, mount[2] + 9 * D))
        p.mass(head, dark, part="cab", group="mirrors", role="form")
        inner = head.face("left" if sx > 0 else "right")
        p.beam(mount, inner.at(inner.width / 2, D), 0.04, 0.04, chrome, part="cab", group="mirrors", role="form",
               name="mirror_arm")
        p.beam(side.at(M, 6 * D), inner.at(inner.width / 2, 7 * D), 0.03, 0.03, chrome, part="cab",
               group="mirror_arms", role="detail", name="mirror_arm_upper")

        # steps under the door: two stringers from the cab floor, two treads between them
        ya = bo.snap(tub_side.at(door.a0 + D, 0.0)[1], D)
        yb = bo.snap(tub_side.at(door.a1 - D, 0.0)[1], D)
        xr = tk.mirror(sx, W - 2 * D, W + D)
        step = tk.finish(s, "steel_dark", "metal_dark")
        for ys in ((ya, ya + D), (yb - D, yb)):
            p.mass(box(f"step_stringer_{name}", xr, ys, (tk.CAB_FLOOR - 9 * D, tk.CAB_FLOOR)), step, part="cab",
                   group="steps", role="detail")
        for z in (tk.CAB_FLOOR - 9 * D, tk.CAB_FLOOR - 5 * D):
            p.mass(box(f"step_{name}", xr, (ya + D, yb - D), (z, z + D)), step, part="cab", group="steps",
                   role="detail")

    roof = house.face("top")
    for k in range(5):                                                     # roof marker lights along the front
        p.lamp_on(roof, D / 2, "lamp_amber", part="cab", group="markers",
                  at=(roof.width * (k + 1) / 6, 1.5 * D), name="roof_marker")

    # ------------------------------------------------------------------ bonnet: block → tapered loft, grille, lights
    nose = box("nose", (-4 * M, 4 * M), tk.NOSE_Y, (3 * M, TUB_TOP))
    p.mass(nose, paint, part="cab", until=1)
    bonnet = Mass.loft("bonnet", *tk.NOSE_Y, (-4 * M + D, 4 * M - D, 3 * M + D, TUB_TOP - 3 * D),
                       (-4 * M, 4 * M, 3 * M + D, TUB_TOP))
    p.mass(bonnet, paint, part="cab", group="nose", role="form")
    face = bonnet.face("front")
    grille = p.region(face.rect(face.width / 2 - 8 * D, face.width / 2 + 8 * D, 2 * D, face.height - D, "grille"))
    p.panel(grille, dark, part="cab", group="nose", role="structure", thickness=0.02)
    p.frame(grille, chrome, part="cab", group="grille_surround", role="accent", width=0.04, thickness=0.035)
    lift = bo.mul(face.outward, 0.03)                                     # slats half sunk into the grille
    for k in range(5):
        b = grille.b0 + (grille.b1 - grille.b0) * (k + 0.5) / 5
        p.beam(bo.add(face.at(grille.a0 + D / 2, b), lift), bo.add(face.at(grille.a1 - D / 2, b), lift), 0.03, 0.025,
               tk.finish(s, "steel", "metal_steel"), part="cab", group="grille_slats", role="detail", name="slat")
    for a0 in (D, face.width - 5 * D):
        lamp = p.region(face.rect(a0, a0 + 4 * D, 2 * D, 6 * D, f"headlight_{a0:.2f}"))
        p.panel(lamp, "lamp_yellow", part="cab", group="nose", role="structure", thickness=0.04)
    for a in (2.5 * D, face.width - 2.5 * D):
        p.lamp_on(face, D / 2, "lamp_amber", part="cab", group="turn_signals", at=(a, 8 * D), name="turn_signal")

    fm = p.port("front_mount", nose.face("front").at(4 * M, 0.0))
    bumper = box("bumper", (-W, W), (fm[1] - M, fm[1] + D), (fm[2] - 4 * D, fm[2] + 2 * D))
    p.mass(bumper, chrome, part="cab", group="bumper", role="form")
    bf = bumper.face("front")
    plate = p.region(bf.rect(bf.width / 2 - 4 * D, bf.width / 2 + 4 * D, 1.5 * D, bf.height - 1.5 * D, "plate"))
    p.panel(plate, "reflector_white", part="cab", group="bumper", role="accent", thickness=0.01)

    # ------------------------------------------------------------------ fenders over the front wheels
    ay = tk.AXLES["front"]
    wheel_top = 2 * tk.WHEEL_R
    for sx, name in ((-1, "right"), (1, "left")):
        fx = tk.mirror(sx, tk.WHEEL_X - 3 * D, tk.WHEEL_X + 3 * D)
        p.mass(box(f"fender_{name}", fx, (ay - tk.WHEEL_R - 2 * D, y0), (wheel_top + D, wheel_top + 2 * D)), paint,
               part="cab", group="fenders", role="structure")
        p.mass(box(f"fender_lip_{name}", fx, (ay - tk.WHEEL_R - 2 * D, ay - tk.WHEEL_R - D),
                   (wheel_top - 3 * D, wheel_top + D)), paint, part="cab", group="fenders", role="structure")
        p.mass(box(f"fender_flare_{name}", tk.mirror(sx, tk.WHEEL_X + 3 * D, tk.WHEEL_X + 4 * D),
                   (ay - tk.WHEEL_R - D, ay + tk.WHEEL_R), (wheel_top - 2 * D, wheel_top + 2 * D)), dark, part="cab",
               group="fenders", role="accent")
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), origin=tk.ANCHORS[ANCHOR])
