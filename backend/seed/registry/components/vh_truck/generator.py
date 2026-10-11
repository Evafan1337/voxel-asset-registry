"""Box truck with a semi-bonneted cab as a blockout plan: one skeleton refined stage by stage.

Front −Y, left side +X (the fuel tank side), stands on its wheels at z = 0. Stage 1 is seven
masses: bonnet, cab, cargo box, chassis frame, fuel tank, two axles and four wheel blocks.
Everything later is derived from their faces, regions and ports:
- axle_front / axle_rear on the centre line at wheel height, wheel_* ports at the wheel centres;
  the twin rear wheels sit one width + DETAIL inboard of the outer ones;
- front_mount — bottom of the bonnet front: bumper and number plate hang from it;
- mirror_left / mirror_right — top front corners of the cab tub: mirror arms start there;
- tank_mount — on the right side of the frame: tank bracket and straps;
- body_floor — centre of the cargo box floor: the subframe carries the box down to the frame.
The cargo box is solid on stages 1–2; from stage 3 its frame (posts, rails) runs on the stage-1
edges and the panels sit one DETAIL inside it. No part lies flush with a differently coloured face
facing the same way — such pairs share a depth and flicker (builder/zfight.py finds them).
`part` isolates a key block: cab, body (cargo box), wheel (front right wheel with its fender),
chassis (the fuel tank). Pure-Python plan (builder/blockout.py); build() renders it with vehlib."""

from __future__ import annotations

from typing import Any

import blockout as bo
from blockout import Mass, Plan

M, D = bo.MACRO_GRID, bo.DETAIL_GRID                # 0.25 structure · 0.0625 detail

# skeleton on the macro grid
WHEEL_R = 2 * M                                     # the axles sit at z = WHEEL_R
WHEEL_W = 5 * D
WHEEL_X = 4 * M                                     # wheel centre planes
AXLES = {"front": -9 * M, "rear": 6 * M}
FRAME_W, FRAME_Y, FRAME_Z = 2 * M, (-10 * M, 11 * M), (2 * M, 4 * M)   # front end inside the bonnet
CAB_W = 4 * M                                       # half width of bonnet and cab
NOSE_Y, NOSE_Z = (-11 * M, -7 * M), (3 * M, 6 * M)
CAB_Y, CAB_Z = (-7 * M, -2 * M), (4 * M, 10 * M)
TUB_Z = 7 * M                                       # tub / greenhouse split (stage 2+)
SCREEN_TOP_Y = -6 * M                               # top edge of the windscreen
BODY_W, BODY_Y, BODY_Z = 5 * M, (-1 * M, 11 * M), (5 * M, 12 * M)
MEMBER = 2 * D                                      # cargo box posts and rails
SIDES = ((-1, "left"), (1, "right"))


def mirror(sx: int, x0: float, x1: float) -> tuple[float, float]:
    """x range of a part on side sx (+1 right, −1 left) given its right-side range."""
    return (x0, x1) if sx > 0 else (-x1, -x0)


def box(name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Mass:
    return Mass.box(name, (x[0], y[0], z[0]), (x[1], y[1], z[1]))


def plan(params: dict[str, Any]) -> Plan:
    s = params["stage"]
    paint, color, trim, stripe = params["cab"], params["body"], params["trim"], params["stripe"]
    p = Plan(s)

    # ------------------------------------------------------------------ chassis: block → rails, springs, members
    frame = box("frame", (-FRAME_W, FRAME_W), FRAME_Y, FRAME_Z)
    p.mass(frame, "soot", part="frame", group="chassis", until=1)
    axles = {tag: p.port(f"axle_{tag}", (0.0, y, WHEEL_R)) for tag, y in AXLES.items()}
    side = frame.face("right")
    tank_mount = p.port("tank_mount", side.at(-FRAME_Y[0], M))                 # frame side at y = 0
    rail_x = (FRAME_W - 3 * D, FRAME_W - D)                    # inboard of the twin wheels
    rail_y = (FRAME_Y[0] + D, FRAME_Y[1] - D)                  # ends inside the bonnet and the rear bar
    for sx, name in SIDES:
        p.mass(box(f"rail_{name}", mirror(sx, *rail_x), rail_y, (FRAME_Z[1] - M, FRAME_Z[1])), "soot", part="frame",
               group="chassis", role="form")
        for tag, axle in axles.items():                                            # leaf springs on the axles
            p.mass(box(f"spring_{tag}_{name}", mirror(sx, *rail_x), (axle[1] - 4 * D, axle[1] + 4 * D),
                       (axle[2] + D, FRAME_Z[1] - M)), trim, part="frame", group="chassis", role="form")
    for k in range(5):
        y = bo.lerp((0.0, FRAME_Y[0] + M, 0.0), (0.0, FRAME_Y[1] - M, 0.0), k / 4)[1]
        p.mass(box(f"cross_member_{k}", (-rail_x[0], rail_x[0]), (y - D, y + D), (FRAME_Z[1] - M, FRAME_Z[1] - 2 * D)),
               "soot", part="frame", group="chassis", role="structure")

    # ------------------------------------------------------------------ axles and wheels on their ports
    for tag, axle in axles.items():
        p.cylinder("x", (-WHEEL_X, WHEEL_X), (axle[1], axle[2]), D, trim, part="wheels", group="axles", role="mass",
                   sides=8, name=f"axle_{tag}")
        for sx, name in SIDES:
            port = p.port(f"wheel_{tag}_{name}", (sx * WHEEL_X, axle[1], axle[2]))
            key = "wheel" if (tag, sx) == ("front", 1) else "wheels"
            p.wheel(port, WHEEL_R, WHEEL_W, side=sx, part=key, group="wheels", name=f"wheel_{tag}_{name}")
            if tag == "rear":
                twin = bo.add(port, (-sx * (WHEEL_W + D), 0.0, 0.0))
                p.wheel(twin, WHEEL_R, WHEEL_W, side=sx, part="wheels", group="twin_wheels", role="structure",
                        name=f"twin_{name}")
            else:                                                                  # fender: top plate and front lip
                fx = mirror(sx, WHEEL_X - 3 * D, WHEEL_X + 3 * D)
                top = 2 * WHEEL_R
                p.mass(box(f"fender_{name}", fx, (port[1] - WHEEL_R - D, CAB_Y[0]), (top + D, top + 2 * D)), paint,
                       part=key, group="fenders", role="structure")
                p.mass(box(f"fender_lip_{name}", fx, (port[1] - WHEEL_R - D, port[1] - WHEEL_R),
                           (NOSE_Z[0] + D, top + D)), paint, part=key, group="fenders", role="structure")

    # ------------------------------------------------------------------ bonnet: block → tapered loft, bumper below
    nose = box("nose", (-CAB_W, CAB_W), NOSE_Y, NOSE_Z)
    p.mass(nose, paint, part="cab", until=1)
    bonnet = Mass.loft("bonnet", *NOSE_Y, (-CAB_W + 2 * D, CAB_W - 2 * D, NOSE_Z[0] + D, NOSE_Z[1] - 2 * D),
                       (-CAB_W + D, CAB_W - D, NOSE_Z[0] + D, NOSE_Z[1]))
    p.mass(bonnet, paint, part="cab", group="nose", role="form")
    front_mount = p.port("front_mount", nose.face("front").at(CAB_W, 0.0))
    fy, fz = front_mount[1], front_mount[2]
    bumper = box("bumper", (-CAB_W, CAB_W), (fy - 3 * D, fy + D), (fz - 3 * D, fz + D))
    p.mass(bumper, trim, part="cab", group="bumper", role="form")

    face = bonnet.face("front")
    grille = p.region(face.rect(face.width / 2 - 8 * D, face.width / 2 + 8 * D, 2 * D, face.height - 2 * D, "grille"))
    p.panel(grille, "soot", part="cab", group="nose", role="structure", thickness=0.02)
    lift = bo.mul(face.outward, 0.03)                                             # slats half sunk into the grille
    for k in range(4):
        b = grille.b0 + (grille.b1 - grille.b0) * (k + 0.5) / 4
        p.beam(bo.add(face.at(grille.a0 + D / 2, b), lift), bo.add(face.at(grille.a1 - D / 2, b), lift), 0.025, 0.025,
               "steel", part="cab", group="grille_slats", role="detail", name="slat")
    for a0 in (D, face.width - 5 * D):
        lamp = p.region(face.rect(a0, a0 + 4 * D, 2 * D, 5 * D, f"headlight_{a0:.2f}"))
        p.panel(lamp, "plaster", part="cab", group="nose", role="structure", thickness=0.04)
    for a in (3 * D, face.width - 3 * D):
        p.lamp_on(face, D / 2, "signal_orange", part="cab", group="nose", at=(a, 7 * D), name="turn_signal")
    plate_face = bumper.face("front")
    plate = p.region(plate_face.rect(plate_face.width / 2 - 4 * D, plate_face.width / 2 + 4 * D, D / 2,
                                     plate_face.height - D / 2, "plate"))
    p.panel(plate, "plaster", part="cab", group="bumper", role="accent", thickness=0.01)

    # ------------------------------------------------------------------ cab: block → tub + greenhouse wedge
    cab = box("cab", (-CAB_W, CAB_W), CAB_Y, CAB_Z)
    p.mass(cab, paint, part="cab", until=1)
    tub = box("tub", (-CAB_W, CAB_W), CAB_Y, (CAB_Z[0], TUB_Z))
    greenhouse = Mass.wedge("greenhouse", (-CAB_W, CAB_W, *CAB_Y), (-CAB_W + D, CAB_W - D, SCREEN_TOP_Y, CAB_Y[1]),
                            TUB_Z, CAB_Z[1])
    p.mass(tub, paint, part="cab", group="cab", role="form")
    p.mass(greenhouse, paint, part="cab", group="cab", role="form")

    front = greenhouse.face("front")
    shield = p.region(front.span(D, D, front.height - D, "windscreen"))
    p.panel(shield, "glass", part="cab", group="cab", role="structure")
    p.frame(shield, trim, part="cab", group="cab_frames", role="detail", width=0.04)
    centre = (shield.a0 + shield.a1) / 2
    lift = bo.mul(front.outward, 0.02)                                            # wipers half sunk into the glass
    for sx in (-1, 1):
        pivot = front.at(centre + sx * 2 * D, shield.b0 + D / 2)
        tip = front.at(centre + sx * 8 * D, shield.b0 + 7 * D)
        p.beam(bo.add(pivot, lift), bo.add(tip, lift), 0.02, 0.025, "soot", part="cab", group="wipers", role="detail",
               name="wiper")

    for sx, name in SIDES:
        gh_side, tub_side = greenhouse.face(name), tub.face(name)
        band = gh_side.span(2 * D, 2 * D, gh_side.height - 2 * D, f"side_{name}")
        window = p.region(band.sub(0.0, 0.72, 0.0, 1.0, f"window_{name}"))
        p.panel(window, "glass", part="cab", group="cab", role="structure")
        p.frame(window, trim, part="cab", group="cab_frames", role="detail", width=0.03)
        # the door on the tub right under the window: the same a-range, projected onto the tub face
        a0, a1 = tub_side.local(window.corners[0])[0], tub_side.local(window.corners[1])[0]
        door = p.region(tub_side.rect(a0, a1, D, tub_side.height - D, f"door_{name}"))
        p.frame(door, "soot", part="cab", group="cab_frames", role="structure", width=0.02, thickness=0.015)
        p.panel(door.sub(0.78, 0.94, 0.55, 0.7, f"handle_{name}"), "steel", part="cab", group="cab_frames",
                role="detail", thickness=0.03)

        # mirror: head beside the A-pillar on an arm from the tub corner, a second arm from the greenhouse
        mount = p.port(f"mirror_{name}", tub_side.at(M, tub_side.height))
        hx = mirror(sx, CAB_W + 2 * D, CAB_W + M)
        head = box(f"mirror_{name}", hx, (mount[1] - 2 * D, mount[1]), (mount[2] - D, mount[2] + 6 * D))
        p.mass(head, "soot", part="cab", group="mirrors", role="form")
        inner = head.face("left" if sx > 0 else "right")                          # the face toward the cab
        p.beam(mount, inner.at(inner.width / 2, 2 * D), 0.04, 0.04, trim, part="cab", group="mirrors", role="form",
               name="mirror_arm")
        p.beam(gh_side.at(M, 4 * D), inner.at(inner.width / 2, 5 * D), 0.03, 0.03, trim, part="cab",
               group="mirror_arms", role="detail", name="mirror_arm_upper")

        # steps under the door: two stringers from the cab floor, two treads between them
        y0 = bo.snap(tub_side.at(door.a0 + D, 0.0)[1], D)
        y1 = bo.snap(tub_side.at(door.a1 - D, 0.0)[1], D)
        sxr = mirror(sx, CAB_W - D, CAB_W + 2 * D)
        for ya, yb in ((y0, y0 + D), (y1 - D, y1)):
            p.mass(box(f"step_stringer_{name}", sxr, (ya, yb), (CAB_Z[0] - 9 * D, CAB_Z[0])), trim, part="cab",
                   group="steps", role="detail")
        for z in (CAB_Z[0] - 9 * D, CAB_Z[0] - 5 * D):
            p.mass(box(f"step_{name}", sxr, (y0 + D, y1 - D), (z, z + D)), trim, part="cab", group="steps",
                   role="detail")

    roof = greenhouse.face("top")
    visor = box("visor", (-CAB_W + 2 * D, CAB_W - 2 * D), (SCREEN_TOP_Y - 3 * D, SCREEN_TOP_Y + D),
                (CAB_Z[1], CAB_Z[1] + D))
    p.mass(visor, trim, part="cab", group="visor", role="accent")
    vt = visor.face("top")
    for a in (vt.width / 2 - 6 * D, vt.width / 2, vt.width / 2 + 6 * D):
        p.lamp_on(vt, D / 2, "signal_orange", part="cab", group="visor", at=(a, vt.height / 2), name="roof_marker")
    foot = roof.at(roof.width - 3 * D, roof.height - 3 * D)
    p.beam(foot, bo.add(foot, (0.0, D, 8 * D)), 0.025, 0.025, "soot", part="cab", group="antenna", role="accent",
           name="antenna", asym=True)

    # ------------------------------------------------------------------ cargo box: solid → framed panels
    body = box("body", (-BODY_W, BODY_W), BODY_Y, BODY_Z)
    p.mass(body, color, part="body", until=2)
    floor = p.port("body_floor", body.face("bottom").center)
    p.mass(box("subframe", (-FRAME_W - 2 * D, FRAME_W + 2 * D), (BODY_Y[0] + 2 * D, BODY_Y[1] - 2 * D),
               (FRAME_Z[1], floor[2])), trim, part="body", group="subframe", role="form")
    panels = box("body_panels", (-BODY_W + D, BODY_W - D), (BODY_Y[0] + D, BODY_Y[1] - D),
                 (BODY_Z[0] + D, BODY_Z[1] - D))
    p.mass(panels, color, part="body", group="body", role="structure")
    ends = {"front": (BODY_Y[0], BODY_Y[0] + MEMBER), "back": (BODY_Y[1] - MEMBER, BODY_Y[1])}
    levels = {"bottom": (BODY_Z[0], BODY_Z[0] + MEMBER), "top": (BODY_Z[1] - MEMBER, BODY_Z[1])}
    for sx, name in SIDES:
        edge = mirror(sx, BODY_W - MEMBER, BODY_W)
        for end, ys in ends.items():
            p.mass(box(f"post_{end}_{name}", edge, ys, BODY_Z), trim, part="body", group="body", role="structure")
        for level, zs in levels.items():
            p.mass(box(f"rail_{level}_{name}", edge, BODY_Y, zs), trim, part="body", group="body", role="structure")
    for end, ys in ends.items():
        for level, zs in levels.items():
            p.mass(box(f"rail_{level}_{end}", (-BODY_W, BODY_W), ys, zs), trim, part="body", group="body",
                   role="structure")

    for sx, name in SIDES:
        face = panels.face(name)
        lo, hi = MEMBER - D, face.width - (MEMBER - D)                             # open span between the posts
        for k in range(1, 8):
            a = lo + (hi - lo) * k / 8
            rib = p.region(face.rect(a - D / 2, a + D / 2, D, face.height - D, f"rib_{name}_{k}"))
            p.panel(rib, trim, part="body", group="ribs", role="detail", thickness=D / 2)
        band = p.region(face.rect(4 * D, face.width - 4 * D, 8 * D, 10 * D, f"stripe_{name}"))
        p.panel(band, stripe, part="body", group="stripe", role="accent", thickness=0.05, offset=-0.01)
        outer = body.face(name)
        for a in (0.25, 0.5, 0.75):
            p.lamp_on(outer, 0.04, "signal_orange", part="body", group="markers", at=(outer.width * a, D),
                      name="side_marker")
    top = body.face("top")
    for a in (MEMBER / 2, top.width - MEMBER / 2):
        for b in (MEMBER / 2, top.height - MEMBER / 2):
            p.lamp_on(top, 0.05, "signal_orange", part="body", group="markers", at=(a, b), name="top_marker")

    back = panels.face("back")                                                     # rear doors
    seam = p.region(back.rect(back.width / 2 - D / 4, back.width / 2 + D / 4, D, back.height - D, "door_seam"))
    p.panel(seam, trim, part="body", group="rear_doors", role="detail", thickness=0.02)
    for a0 in (D, back.width - 3 * D):
        for b0 in (3 * D, back.height - 5 * D):
            hinge = p.region(back.rect(a0, a0 + 2 * D, b0, b0 + 2 * D, f"hinge_{a0:.2f}_{b0:.2f}"))
            p.panel(hinge, trim, part="body", group="rear_doors", role="detail", thickness=0.04)
    lift = bo.mul(back.outward, 0.035)
    for x in (-12 * D, -6 * D, 6 * D, 12 * D):                                     # lock bars, mirrored pairs
        a = back.local((x, 0.0, BODY_Z[0]))[0]
        p.beam(bo.add(back.at(a, 3 * D), lift), bo.add(back.at(a, back.height - 3 * D), lift), 0.04, 0.04, "steel",
               part="body", group="rear_doors", role="accent", name="lock_bar")

    # ------------------------------------------------------------------ fuel tank on the right of the frame
    tx, tz = tank_mount[0] + M, tank_mount[2]
    p.mass(box("tank", (tank_mount[0], tank_mount[0] + 2 * M), (-2 * M, 2 * M), (tz - M, tz + M)), trim,
           part="chassis", group="tank", until=2, asym=True)
    p.cylinder("y", (-7 * D, 7 * D), (tx, tz), M, "steel", part="chassis", group="tank", role="structure", sides=14,
               name="tank", asym=True)
    p.mass(box("tank_bracket", (rail_x[1], tank_mount[0] + D), (-2 * D, 2 * D), (tz - D, tz + D)), trim,
           part="chassis", group="tank_bracket", role="structure", asym=True)
    for y in (-5 * D, 4 * D):
        p.mass(box("tank_strap", (tank_mount[0], tx + M + D), (y, y + D), (tz - M - D, tz + M + D)), trim,
               part="chassis", group="tank_straps", role="detail", asym=True)
    p.cylinder("z", (tz + M - D, tz + M + 1.5 * D), (tx, 2 * D), D, "soot", part="chassis", group="tank",
               role="accent", sides=8, name="filler_cap", asym=True)

    # ------------------------------------------------------------------ rear end, mudguards, side guard, exhaust
    rear_bar = box("rear_bar", (-CAB_W, CAB_W), (FRAME_Y[1] - 2 * D, FRAME_Y[1] + D),
                   (FRAME_Z[0] + 3 * D, FRAME_Z[0] + 6 * D))
    p.mass(rear_bar, trim, part="frame", group="rear_bar", role="structure")
    rb = rear_bar.face("back")
    for a in (2 * D, rb.width - 2 * D):
        p.lamp_on(rb, D, "signal_red", part="frame", group="rear_bar", at=(a, rb.height / 2), role="structure",
                  name="tail_light")
    ry = axles["rear"][1]
    for sx, name in SIDES:
        gx = mirror(sx, rail_x[1], WHEEL_X + 3 * D)
        top = 2 * WHEEL_R
        p.mass(box(f"mudguard_{name}", gx, (ry - WHEEL_R - 3 * D, ry + WHEEL_R + 3 * D), (top + D, top + 2 * D)),
               "soot", part="frame", group="mudguards", role="structure")
        p.mass(box(f"mud_flap_{name}", gx, (ry + WHEEL_R + D, ry + WHEEL_R + 2 * D), (WHEEL_R / 2, top + D)), "soot",
               part="frame", group="mudguards", role="accent")

    gy = (CAB_Y[1] + 2 * D, ry - WHEEL_R - D)                                      # side guard on the left
    gx = (-BODY_W + D, -BODY_W + 2 * D)
    for z in (FRAME_Z[0] + 2 * D, FRAME_Z[0] + 6 * D):
        p.mass(box("guard_bar", gx, gy, (z, z + D)), trim, part="frame", group="side_guard", role="detail", asym=True)
    for y in (gy[0] + D, gy[1] - 2 * D):
        p.mass(box("guard_post", gx, (y, y + D), (FRAME_Z[0] + 2 * D, FRAME_Z[0] + 7 * D)), trim, part="frame",
               group="side_guard", role="detail", asym=True)
        p.mass(box("guard_arm", (gx[1], -rail_x[1]), (y, y + D), (FRAME_Z[0] + 6 * D, FRAME_Z[0] + 7 * D)), trim,
               part="frame", group="side_guard", role="detail", asym=True)

    stack = (-CAB_W + 3 * D, (CAB_Y[1] + BODY_Y[0]) / 2)                          # exhaust in the cab–box gap
    p.cylinder("z", (FRAME_Z[1] - 2 * D, CAB_Z[1] + 3 * D), stack, D, "steel_dark", part="frame", group="exhaust",
               role="accent", sides=8, name="exhaust_stack", asym=True)
    p.cylinder("z", (CAB_Z[1] + D, CAB_Z[1] + M), stack, 1.5 * D, "soot", part="frame", group="exhaust", role="accent",
               sides=8, name="exhaust_cap", asym=True)
    p.beam((-rail_x[1], stack[1], FRAME_Z[1] - 2 * D), (stack[0], stack[1], FRAME_Z[1] - 2 * D), 0.08, 0.08,
           "steel_dark", part="frame", group="exhaust", role="accent", name="exhaust_pipe", asym=True)
    p.beam((stack[0], stack[1] - D, CAB_Z[1] - 8 * D), (stack[0], CAB_Y[1], CAB_Z[1] - 8 * D), 0.04, 0.04, trim,
           part="frame", group="exhaust", role="accent", name="exhaust_bracket", asym=True)
    return p


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    import vehlib

    return vehlib.render(plan(params), params["part"])
