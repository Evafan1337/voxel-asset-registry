"""Light utility helicopter as a blockout plan: one skeleton refined stage by stage.

Front −Y. Stage 1 is five masses: cabin wedge, tail boom + fin, mast with the rotor, skid rails,
tail-rotor axle. Everything later is derived from their faces, regions and ports:
- rotor_mount = centre of the cabin top; the mast rises from it to the rotor hub;
- tail_mount = on the cabin back face; the boom starts exactly there;
- tail_rotor_mount beside the fin at the boom end;
- skid legs dock on ports on the cabin bottom face.
`part` isolates a key block: cabin, rotor, tail_rotor, skids. The plan is plain Python
(builder/blockout.py) — tests read it without Blender; build() renders it with vehlib."""

from __future__ import annotations

import math
from typing import Any

import blockout as bo
from blockout import Mass, Plan, Rotor

M, D = bo.MACRO_GRID, bo.DETAIL_GRID                # 0.25 structure · 0.0625 detail

# skeleton on the macro grid
CABIN_W = 3 * M                                     # half width
CABIN_Y = (-7 * M, 1 * M)                           # nose .. back face
CABIN_Z = (2 * M, 8 * M)                            # belly .. roof
ROOF_Y0 = -5 * M                                    # top of the windscreen
ROOF_W = CABIN_W - 2 * D                            # the canopy tapers inward
TUB_Z = 4 * M                                       # tub / canopy split (stage 2+)
TAIL_END_Y = 14 * M
MAST_H = 2 * M
ROTOR_R = 10 * M
TAIL_ROTOR_R = 2 * M
SKID_Y = (-7 * M, 2 * M)                            # skid rails along y
SKID_IN, SKID_OUT = CABIN_W, CABIN_W + M            # rail band under the cabin sides


def mirror_box(sx: int, x0: float, x1: float) -> tuple[float, float]:
    """x range of the part on side sx (+1 right, −1 left) given its right-side range."""
    return (x0, x1) if sx > 0 else (-x1, -x0)


def plan(params: dict[str, Any]) -> Plan:
    s = params["stage"]
    color, trim, tip = params["color"], params["trim"], params["tip"]
    turns = params["rotor_turns"]
    p = Plan(s)

    # ------------------------------------------------------------------ cabin: one wedge → tub + canopy
    cabin = Mass.wedge("cabin", (-CABIN_W, CABIN_W, *CABIN_Y), (-ROOF_W, ROOF_W, ROOF_Y0, CABIN_Y[1]), *CABIN_Z)
    p.mass(cabin, color, part="cabin", until=1)
    tub = Mass.wedge("tub", (-CABIN_W, CABIN_W, CABIN_Y[0] + M, CABIN_Y[1]), (-CABIN_W, CABIN_W, *CABIN_Y),
                     CABIN_Z[0], TUB_Z)
    canopy = Mass.wedge("canopy", (-CABIN_W, CABIN_W, *CABIN_Y), (-ROOF_W, ROOF_W, ROOF_Y0, CABIN_Y[1]),
                        TUB_Z, CABIN_Z[1])
    p.mass(tub, color, part="cabin", group="cabin", role="form")
    p.mass(canopy, "glass" if s == 2 else trim, part="cabin", group="cabin", role="form")

    top, back, bottom = cabin.face("top"), cabin.face("back"), cabin.face("bottom")
    rotor_mount = p.port("rotor_mount", top.center)
    tail_mount = p.port("tail_mount", back.at(back.width / 2, 4 * M))
    hub = p.port("rotor_hub", bo.add(rotor_mount, (0.0, 0.0, MAST_H)))
    legs = {}
    for sx, name in ((-1, "left"), (1, "right")):
        a = CABIN_W + sx * 2 * M                                                   # 1 m apart, centred
        for tag, b in (("front", 3 * M), ("rear", 7 * M)):
            legs[(sx, tag)] = p.port(f"skid_{tag}_{name}", bottom.at(a, b))

    # ------------------------------------------------------------------ main rotor on the mast
    p.cylinder("z", (rotor_mount[2], hub[2]), (hub[0], hub[1]), D, trim, part="rotor", group="rotor", role="mass",
               sides=8, name="mast")
    p.cylinder("z", (rotor_mount[2], rotor_mount[2] + 2 * D), (hub[0], hub[1]), 2 * D, trim, part="rotor",
               group="rotor_base", role="structure", sides=8, name="mast_base")
    p.cylinder("z", (hub[2] - 4 * D, hub[2] - 3 * D), (hub[0], hub[1]), 2.5 * D, "steel", part="rotor",
               group="rotor_base", role="detail", sides=12, name="swashplate")
    tips = {1: None, 2: None, 3: "plaster"}.get(s, tip)
    p.rotor(Rotor("main_rotor", "rotor", "rotor", hub, "XY", ROTOR_R, 4, 0.2, s, "steel_dark" if s == 1 else "soot",
                  tips, trim, turns, phase=math.pi / 4))

    # ------------------------------------------------------------------ engine hump (silhouette, stage 2)
    engine = Mass.box("engine", (-1.5 * M, rotor_mount[1] + M, CABIN_Z[1]),
                      (1.5 * M, CABIN_Y[1] + M, CABIN_Z[1] + 5 * D))
    p.mass(engine, trim, part="cabin", role="form")
    for sx, side in ((-1, "left"), (1, "right")):
        intake = engine.face(side).span(D, D, engine.face(side).height - D, f"intake_{side}")
        p.region(intake.sub(0.1, 0.45, 0.0, 1.0, f"intake_{side}"))
        p.panel(p.regions[f"intake_{side}"], "soot", part="cabin", group="engine", role="detail", thickness=0.02)
    exhaust_c = engine.face("back").center
    p.cylinder("y", (exhaust_c[1], exhaust_c[1] + 3 * D), (exhaust_c[0], exhaust_c[2]), 1.2 * D, "soot",
               part="cabin", group="engine", role="accent", sides=8, name="exhaust")
    p.lamp_on(engine.face("top"), 0.8 * D, "signal_red", part="cabin", group="engine", name="beacon")

    # ------------------------------------------------------------------ glazing: regions of the canopy faces
    front = canopy.face("front")
    shield = p.region(front.span(D, D, front.height - D, "windscreen"))
    panes = [p.region(r) for r in shield.split_a(2, 2 * D, "windscreen")]
    for r in panes:
        p.panel(r, "glass", part="cabin", group="cabin", role="structure")
        p.frame(r, trim, part="cabin", group="cabin_frames", role="detail", width=0.04)
    for side in ("left", "right"):
        face = canopy.face(side)
        band = face.span(D, 2 * D, face.height - 2 * D, f"side_{side}")
        front_win, door_win = band.split_a(2, 2 * D, f"window_{side}")
        for r in (front_win, door_win):
            p.region(r)
            p.panel(r, "glass", part="cabin", group="cabin", role="structure")
            p.frame(r, trim, part="cabin", group="cabin_frames", role="detail", width=0.04)
        # the door on the tub right under the door window: same a-range, projected onto the tub face
        tub_face = tub.face(side)
        a0 = tub_face.local(door_win.corners[0])[0]
        a1 = tub_face.local(door_win.corners[1])[0]
        door = p.region(tub_face.rect(a0, a1, D, tub_face.height - D, f"door_{side}"))
        p.frame(door, "soot", part="cabin", group="cabin_frames", role="structure", width=0.02, thickness=0.015)
        handle = door.sub(0.78, 0.92, 0.55, 0.65, f"handle_{side}")
        p.panel(handle, "steel", part="cabin", group="cabin_frames", role="detail", thickness=0.03)
        stripe = p.region(tub_face.span(D, 2 * D, 3 * D, f"stripe_{side}"))
        p.panel(stripe, "plaster", part="cabin", group="cabin_frames", role="accent", thickness=0.01)
    p.lamp_on(tub.face("front"), 0.8 * D, "plaster", part="cabin", group="cabin", name="landing_light")

    # ------------------------------------------------------------------ tail: boom from tail_mount, fin, stabiliser
    ty, tz = tail_mount[1], tail_mount[2]
    boom = Mass.loft("tail_boom", ty, TAIL_END_Y, (-M, M, tz - M, tz + M), (-2 * D, 2 * D, tz - 2 * D, tz + 2 * D))
    p.mass(boom, color, part="tail", group="tail", until=2)
    tail_end = p.port("tail_end", (0.0, TAIL_END_Y, tz))
    fin_mass = Mass.wedge("fin", (-2 * D, 2 * D, TAIL_END_Y - M, TAIL_END_Y + M),
                          (-2 * D, 2 * D, TAIL_END_Y, TAIL_END_Y + M), tz - M, tz + 3 * M)
    p.mass(fin_mass, color, part="tail", group="tail", until=1)
    fin = Mass.wedge("fin_blade", (-D, D, TAIL_END_Y - M, TAIL_END_Y + M), (-D, D, TAIL_END_Y, TAIL_END_Y + M),
                     tz - M, tz + 3 * M)
    p.mass(fin, color, part="tail", group="tail", role="form")
    if s >= 3:                                                           # lattice on the boom's own edges
        c = boom.corners
        w = 0.06
        for i in range(4):
            p.beam(c[i], c[i + 4], w, w, color, part="tail", group="tail", role="structure", name="longeron")
        bays = 8
        for k in range(bays):
            t0, t1 = k / bays, (k + 1) / bays
            at = lambda i, t: bo.lerp(c[i], c[i + 4], t)                                   # noqa: E731
            for lo_i, hi_i in ((0, 3), (1, 2)):                                           # side zig-zags
                a, b = (t0, t1) if k % 2 else (t1, t0)
                p.beam(at(lo_i, a), at(hi_i, b), 0.035, 0.035, color, part="tail", group="tail", role="structure")
            for a, b in ((3, 2), (2, 3)):                                                # top X-bracing
                p.beam(at(a, t0), at(b, t1), 0.03, 0.03, color, part="tail", group="tail", role="structure")
            p.beam(at(0, t1), at(1, t1), 0.04, 0.04, trim, part="tail", group="tail", role="detail")
        collar = Mass.box("boom_collar", (-M - D, ty, tz - M - D), (M + D, ty + M, tz + M + D))
        p.mass(collar, trim, part="tail", group="tail", role="structure")
    stab = Mass.box("stabiliser", (-2 * M, TAIL_END_Y - 3 * M, tz - D), (2 * M, TAIL_END_Y - 2 * M, tz))
    p.mass(stab, color, part="tail", role="form")
    for side, lamp_color in (("left", "signal_red"), ("right", "paint_green")):
        p.lamp_on(stab.face(side), 0.6 * D, lamp_color, part="tail", group="stabiliser", name="nav_light")
    for side in ("left", "right"):
        band = fin.face(side).span(D, 8 * D, 10 * D, f"fin_band_{side}")
        p.panel(p.region(band), "paint_yellow", part="tail", group="tail", role="accent", thickness=0.01)
    p.beam(bo.add(tail_end, (0.0, 0.0, -D)), bo.add(tail_end, (0.0, M, -5 * D)), 0.035, 0.035, trim, part="tail",
           group="tail_skid", role="detail", name="tail_skid")
    boom_top = boom.face("top")
    mast_foot = boom_top.at(boom_top.width / 2, 4 * M)                                  # on the boom, 1 m aft
    p.beam(mast_foot, bo.add(mast_foot, (0.0, D, 5 * D)), 0.02, 0.02, "soot", part="tail", group="antenna",
           role="detail", name="antenna")

    # ------------------------------------------------------------------ tail rotor beside the fin
    tr = p.port("tail_rotor_mount", (M, TAIL_END_Y, tz + 2 * M))
    p.cylinder("x", (0.0, tr[0]), (tr[1], tr[2]), D, trim, part="tail_rotor", group="tail_rotor", role="mass",
               sides=8, name="tail_rotor_axle", asym=True)
    gearbox = Mass.box("gearbox", (D, tr[1] - 2 * D, tr[2] - 2 * D), (tr[0] - D, tr[1] + 2 * D, tr[2] + 2 * D))
    p.mass(gearbox, trim, part="tail_rotor", group="tail_gearbox", role="structure", asym=True)
    blades = 2 if s < 4 else 4
    p.rotor(Rotor("tail_rotor", "tail_rotor", "tail_rotor", tr, "YZ", TAIL_ROTOR_R, blades, 0.1,
                  s, color if s == 1 else "soot", tips, trim, 3 * turns, phase=math.radians(15)))

    # ------------------------------------------------------------------ skids: rails → tubes + legs on the cabin ports
    for sx, name in ((-1, "left"), (1, "right")):
        x0, x1 = mirror_box(sx, SKID_IN, SKID_OUT)
        rail = Mass.box(f"skid_{name}", (x0, SKID_Y[0], 0.0), (x1, SKID_Y[1], M))
        p.mass(rail, "soot", part="skids", group="skids", until=1)
        xc = (x0 + x1) / 2
        r = D
        p.cylinder("y", (SKID_Y[0] + M, SKID_Y[1]), (xc, r), r, "soot", part="skids", group="skids", role="form",
                   sides=8, name="skid_tube")
        p.beam((xc, SKID_Y[0] + M, r), (xc, SKID_Y[0] + r, 3 * D), 2 * r, 2 * r, "soot", part="skids", group="skids",
               role="structure", name="skid_tip")
        for tag in ("front", "rear"):
            port = legs[(sx, tag)]
            p.beam((xc, port[1], r), port, 0.07, 0.07, trim, part="skids", group="skid_legs", role="form",
                   name="skid_leg")
        front_leg = legs[(sx, "front")]
        on_leg = bo.lerp((xc, front_leg[1], r), front_leg, (M - r) / (front_leg[2] - r))  # the leg at z = M
        p.beam(on_leg, bo.add(on_leg, (sx * 3 * D, 0.0, 0.0)), 0.05, 0.03, trim, part="skids", group="skid_legs",
               role="detail", name="step")
        for y in (SKID_Y[0] + 2 * M, SKID_Y[1] - M):
            p.cylinder("y", (y - D, y + D), (xc, 1.3 * r), 1.3 * r, "steel_dark", part="skids", group="skids",
                       role="accent", sides=12, name="skid_shoe")    # 8 sides would share the tube's facets
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), params["part"])
