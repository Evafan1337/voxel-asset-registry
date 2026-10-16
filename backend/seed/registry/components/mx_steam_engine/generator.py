"""Horizontal mill steam engine: cut-away cylinder with a piston, crosshead in guides, connecting rod,
disc crank with a flywheel, eccentric-driven slide valve, Watt governor, exhaust puffs (level 3).

The engine line runs along X (cylinder at −X, crank at +X) in the plane y = 0; the crankshaft runs
along +Y into the machine, the flywheel sits behind the crank. Every dimension is multiplied by
`size` (k). One kinematics drives every moving part: crank angle phi(t) = 2π·turns·t.

Clearances hold through the whole loop (checked with builder/motion_clearance.py): the guide bars end
just past the crosshead's front dead centre and stand far enough apart for the conrod at its steepest,
the piston stops short of both covers and of the valve chest, and the big end stays inside the crank disc."""

from __future__ import annotations

import math
from typing import Any

from mathutils import Vector

import voxlib as vx

# Unscaled layout, metres (k = 1).
ZK = 1.25            # engine axis height (cylinder, crosshead, crankshaft)
XK = 1.35            # crankshaft
CRANK = 0.32         # crank radius: stroke 0.64 m, rod/crank 5 — the rod tilts at most 11.5°
ROD = 1.6            # connecting rod, pin to pin
PISTON_ROD = 1.3     # crosshead pin to piston centre: the stroke sits mid-bore, 0.1 m short of each cover
GUIDE = 0.2          # guide bar faces from the axis: the conrod swings at most 0.18 inside the bars
SLIPPER = 0.17       # half length of the crosshead slippers
X_FRONT, X_BACK = -1.0, -2.1          # cylinder covers (outer faces)
R_BORE, R_LINER, R_JACKET = 0.35, 0.39, 0.44
CUT = (math.radians(105), math.radians(240))  # the cut-away window, angle in the Y–Z plane (front = 180°)
Y_ECC, ECC, LEAD = 0.25, 0.08, math.radians(120)   # eccentric plane, throw, angle ahead of the crank pin
X_VALVE_ROD_LEN = 2.2
Z_VALVE = ZK + 0.45
R_FLY = 1.15


def hexa(m: vx.MeshBuilder, pts: list[Vector], color: str) -> None:
    """Convex hexahedron from 8 corners: 0–3 around one end, 4–7 the same way around the other."""
    centre = sum(pts, Vector()) / 8
    for face in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        f = [pts[i] for i in face]
        normal = (f[1] - f[0]).cross(f[2] - f[0])
        mid = sum(f, Vector()) / 4
        m.polygon([tuple(p) for p in (f if normal.dot(mid - centre) >= 0 else reversed(f))], color)


def shell(m: vx.MeshBuilder, r_in: float, r_out: float, x0: float, x1: float, zc: float, color: str,
          *, cut: tuple[float, float] | None, sides: int = 20) -> None:
    """Tube along X around (y=0, z=zc), optionally with an angular window left open."""
    for i in range(sides):
        a0, a1 = 2 * math.pi * i / sides, 2 * math.pi * (i + 1) / sides
        if cut and cut[0] <= (a0 + a1) / 2 <= cut[1]:
            continue
        ring = [(r_in, a0), (r_out, a0), (r_out, a1), (r_in, a1)]
        pts = [Vector((x, r * math.cos(a), zc + r * math.sin(a))) for x in (x0, x1) for r, a in ring]
        hexa(m, pts, color)


def build(params: dict[str, Any]) -> "bpy.types.Object":  # noqa: F821
    k, turns = params["size"], params["turns"]
    paint, accent, metal, base_c = params["color"], params["accent"], params["metal"], params["base"]
    zk, xk, r, rod_len = ZK * k, XK * k, CRANK * k, ROD * k
    cut = CUT if params["cutaway"] else None

    def phi(t: float) -> float:
        return 2 * math.pi * turns * t

    def pin(t: float) -> Vector:
        return Vector((xk + r * math.cos(phi(t)), 0.0, zk + r * math.sin(phi(t))))

    def crosshead_x(t: float) -> float:
        p = pin(t)
        return p.x - math.sqrt(rod_len ** 2 - (p.z - zk) ** 2)

    def ecc(t: float) -> Vector:
        a = phi(t) + LEAD
        return Vector((xk + ECC * k * math.cos(a), Y_ECC * k, zk + ECC * k * math.sin(a)))

    def valve_x(t: float) -> float:
        e = ecc(t)
        return e.x - math.sqrt((X_VALVE_ROD_LEN * k) ** 2 - (Z_VALVE * k - e.z) ** 2)

    # ------------------------------------------------------------------ static: plinth, frame, cylinder
    b = vx.MeshBuilder()
    b.box((-2.35 * k, -0.5 * k, 0.0), (2.2 * k, 0.56 * k, 0.3 * k), base_c)                  # plinth (flywheel pit behind)
    b.box((xk - 0.35 * k, 0.88 * k, 0.0), (xk + 0.35 * k, 1.12 * k, 0.3 * k), base_c)          # outboard foot
    b.box((-2.15 * k, -0.4 * k, 0.3 * k), (-0.95 * k, 0.4 * k, zk - 0.41 * k), paint)          # cylinder saddle
    b.box((-0.95 * k, -0.18 * k, 0.3 * k), (xk - 0.3 * k, 0.18 * k, 0.72 * k), paint)          # girder frame
    # slide bars: bolted to the front cover, ending at a bracket just past the slippers' front dead centre
    x_guide = (XK + CRANK - ROD + SLIPPER + 0.1) * k
    for z in (zk + GUIDE * k, zk - (GUIDE + 0.06) * k):
        b.box((X_FRONT * k, -0.13 * k, z), (x_guide, 0.13 * k, z + 0.06 * k), metal)
    for x0, x1 in ((-0.93, -0.83), (x_guide / k - 0.08, x_guide / k)):                     # guide standards
        b.box((x0 * k, -0.13 * k, 0.72 * k), (x1 * k, 0.13 * k, zk - (GUIDE + 0.06) * k), paint)
    b.box((x_guide - 0.08 * k, 0.13 * k, 0.72 * k), (x_guide, 0.17 * k, zk + (GUIDE + 0.06) * k), paint)  # bracket behind
    for y0, y1 in ((0.32, 0.56), (0.88, 1.12)):                                              # main and outboard bearings
        b.box((xk - 0.25 * k, y0 * k, 0.3 * k), (xk + 0.25 * k, y1 * k, zk - 0.1 * k), paint)
        b.box((xk - 0.17 * k, y0 * k, zk + 0.09 * k), (xk + 0.17 * k, y1 * k, zk + 0.17 * k), accent)
        b.box((xk - 0.04 * k, (y0 + y1) / 2 * k - 0.04 * k, zk + 0.17 * k),
              (xk + 0.04 * k, (y0 + y1) / 2 * k + 0.04 * k, zk + 0.27 * k), "brass")       # oil cup
    root = b.to_object("base", semantic_part="base")

    cyl = vx.MeshBuilder()
    x_in0, x_in1 = X_BACK * k + 0.06 * k, X_FRONT * k - 0.06 * k
    shell(cyl, R_BORE * k, R_LINER * k, x_in0, x_in1, zk, "steel_dark", cut=cut)            # bore liner
    shell(cyl, R_LINER * k, R_JACKET * k, x_in0, x_in1, zk, "wood", cut=cut)                # timber lagging
    for x in (0.2, 0.55, 0.9):                                                               # brass bands
        xb = x_in0 + x * (x_in1 - x_in0)
        shell(cyl, R_JACKET * k, R_JACKET * k + 0.02 * k, xb - 0.03 * k, xb + 0.03 * k, zk, "brass", cut=cut)
    for x0, x1 in ((X_BACK, X_BACK + 0.06), (X_FRONT - 0.06, X_FRONT)):                     # covers
        cyl.prism(R_JACKET * k + 0.04 * k, x0 * k, x1 * k, paint, sides=20, center=(0.0, zk), axis="X")
    cyl.prism(0.12 * k, X_FRONT * k, (X_FRONT + 0.12) * k, accent, sides=10, center=(0.0, zk), axis="X")   # gland
    cyl.prism(0.1 * k, (X_BACK - 0.08) * k, X_BACK * k, accent, sides=10, center=(0.0, zk), axis="X")      # tail boss
    # valve chest on the back of the cylinder top (seated in the lagging, clear of the bore), steam pipe, exhaust
    cyl.box((-1.95 * k, 0.02 * k, zk + (R_BORE + 0.02) * k), (-1.15 * k, 0.46 * k, zk + 0.68 * k), paint)
    cyl.box((-1.99 * k, 0.0, zk + 0.66 * k), (-1.11 * k, 0.48 * k, zk + 0.72 * k), accent)
    cyl.prism(0.06 * k, -1.15 * k, -1.03 * k, accent, sides=8, center=(Y_ECC * k, Z_VALVE * k), axis="X")  # valve gland
    cyl.prism(0.08 * k, zk + 0.72 * k, 2.2 * k, "copper", sides=10, center=(-1.3 * k, 0.3 * k))
    cyl.prism(0.08 * k, 0.3 * k, 1.12 * k, "copper", sides=10, center=(2.2 * k, -1.3 * k), axis="Y")   # steam main
    cyl.prism(0.1 * k, 2.1 * k, 2.3 * k, "copper", sides=10, center=(-1.3 * k, 0.3 * k))                 # elbow
    cyl.prism(0.11 * k, 1.0 * k, 1.06 * k, "copper", sides=10, center=(2.2 * k, -1.3 * k), axis="Y")    # flange
    cyl.prism(0.17 * k, -1.2 * k, -1.18 * k, "brass", sides=12, center=(0.3 * k, 1.95 * k), axis="X")    # stop valve wheel
    cyl.prism(0.1 * k, 0.3 * k, 2.65 * k, "soot", sides=10, center=(-2.3 * k, 0.3 * k))      # exhaust stack
    cyl.prism(0.13 * k, 2.6 * k, 2.7 * k, "steel_dark", sides=10, center=(-2.3 * k, 0.3 * k))
    cyl.box((-2.3 * k, 0.22 * k, 0.86 * k), (-2.07 * k, 0.38 * k, 1.0 * k), "soot")          # exhaust elbow into the back cover
    cyl.to_object("cylinder", parent=root, semantic_part="cylinder")

    # ------------------------------------------------------------------ piston, rod and crosshead slide along X
    slide = vx.MeshBuilder()
    g, sl = GUIDE * k, SLIPPER * k
    slide.box((-0.15 * k, -0.11 * k, -g + 0.02 * k), (0.15 * k, 0.11 * k, g - 0.02 * k), metal)    # crosshead
    slide.box((-sl, -0.13 * k, g - 0.03 * k), (sl, 0.13 * k, g), "brass")                          # slippers
    slide.box((-sl, -0.13 * k, -g), (sl, 0.13 * k, -g + 0.03 * k), "brass")
    slide.prism(0.05 * k, -0.15 * k, 0.15 * k, "steel_dark", sides=8, center=(0.0, 0.0), axis="Y")  # gudgeon pin
    slide.prism(0.045 * k, -PISTON_ROD * k, -0.1 * k, "steel", sides=8, center=(0.0, 0.0), axis="X")
    slide.prism((R_BORE - 0.01) * k, (-PISTON_ROD - 0.07) * k, (-PISTON_ROD + 0.07) * k, metal, sides=20,
                center=(0.0, 0.0), axis="X")                                                    # piston
    for dx in (-0.035, 0.035):                                                                   # piston rings
        slide.prism((R_BORE - 0.005) * k, (-PISTON_ROD + dx - 0.012) * k, (-PISTON_ROD + dx + 0.012) * k, "brass",
                    sides=20, center=(0.0, 0.0), axis="X")
    slider = slide.to_object("crosshead", parent=root, location=(crosshead_x(0.0), 0.0, zk), semantic_part="crosshead")

    # ------------------------------------------------------------------ connecting rod: local +X from the small end
    cr = vx.MeshBuilder()
    L = rod_len
    hexa(cr, [Vector(p) for p in ((0.08 * k, -0.04 * k, -0.04 * k), (0.08 * k, 0.04 * k, -0.04 * k),
                                  (0.08 * k, 0.04 * k, 0.04 * k), (0.08 * k, -0.04 * k, 0.04 * k),
                                  (L - 0.11 * k, -0.04 * k, -0.07 * k), (L - 0.11 * k, 0.04 * k, -0.07 * k),
                                  (L - 0.11 * k, 0.04 * k, 0.07 * k), (L - 0.11 * k, -0.04 * k, 0.07 * k))], paint)
    cr.box((-0.09 * k, -0.06 * k, -0.09 * k), (0.09 * k, 0.06 * k, 0.09 * k), metal)              # small end
    cr.box((L - 0.12 * k, -0.07 * k, -0.13 * k), (L + 0.12 * k, 0.07 * k, 0.13 * k), metal)       # big end
    cr.box((L + 0.12 * k, -0.08 * k, -0.13 * k), (L + 0.16 * k, 0.08 * k, 0.13 * k), "brass")     # cap
    conrod = cr.to_object("conrod", parent=root, location=(crosshead_x(0.0), 0.0, zk), semantic_part="conrod")

    # ------------------------------------------------------------------ crank, shaft, eccentric sheave, flywheel
    ck = vx.MeshBuilder()
    ck.prism(0.5 * k, 0.08 * k, 0.18 * k, paint, sides=20, axis="Y")                              # disc crank
    ck.box((-0.44 * k, 0.06 * k, -0.22 * k), (-0.2 * k, 0.2 * k, 0.22 * k), "soot")               # counterweight
    ck.prism(0.07 * k, -0.09 * k, 0.1 * k, "steel", sides=10, center=(0.0, r), axis="Y")          # crank pin
    ck.prism(0.09 * k, 0.18 * k, 1.16 * k, "steel", sides=10, axis="Y")                            # crankshaft
    ek = (ECC * k * math.sin(LEAD), ECC * k * math.cos(LEAD))                                       # (z, x) at phi = 0
    # the sheave covers the shaft (ECC + shaft radius 0.17) so the shaft never shows through the strap
    ck.prism(0.19 * k, (Y_ECC - 0.05) * k, (Y_ECC + 0.05) * k, "steel_dark", sides=14, center=ek, axis="Y")
    crank = ck.to_object("crank", parent=root, location=(xk, 0.0, zk), semantic_part="crank")

    fw = vx.MeshBuilder()
    y0, y1 = 0.62 * k, 0.84 * k
    # rim and the brass band lining it: they meet at one radius, so no inner face is shared (flicker)
    fw.ring((R_FLY - 0.12) * k, R_FLY * k, y0, y1, params["flywheel"], sides=32, axis="Y")
    fw.ring((R_FLY - 0.16) * k, (R_FLY - 0.12) * k, y0 - 0.02 * k, y1 + 0.02 * k, accent, sides=32, axis="Y")
    fw.prism(0.22 * k, y0 - 0.03 * k, y1 + 0.03 * k, params["flywheel"], sides=12, axis="Y")        # hub
    spokes = params["spokes"]
    for i in range(spokes):
        a = 2 * math.pi * (i + 0.5) / spokes
        fw.strut((0.18 * k * math.cos(a), (y0 + y1) / 2, 0.18 * k * math.sin(a)),
                 ((R_FLY - 0.14) * k * math.cos(a), (y0 + y1) / 2, (R_FLY - 0.14) * k * math.sin(a)),
                 0.12 * k, params["flywheel"], depth=0.1 * k)
    fw.to_object("flywheel", parent=crank, semantic_part="flywheel")

    # ------------------------------------------------------------------ valve gear: eccentric rod and valve spindle
    Le = X_VALVE_ROD_LEN * k
    ecc_rod_mesh = vx.MeshBuilder()
    ecc_rod_mesh.box((0.0, -0.025 * k, -0.03 * k), (Le - 0.22 * k, 0.025 * k, 0.03 * k), metal)
    for i in range(14):                                                                            # strap around the sheave
        a0, a1 = 2 * math.pi * i / 14, 2 * math.pi * (i + 1) / 14
        pts = [Vector((Le + rr * math.cos(a), yy, rr * math.sin(a)))
               for yy in (-0.04 * k, 0.04 * k) for rr, a in ((0.2 * k, a0), (0.25 * k, a0), (0.25 * k, a1), (0.2 * k, a1))]
        hexa(ecc_rod_mesh, pts, accent)
    ecc_rod_mesh.box((-0.05 * k, -0.04 * k, -0.05 * k), (0.05 * k, 0.04 * k, 0.05 * k), accent)     # fork
    v0 = Vector((valve_x(0.0), Y_ECC * k, Z_VALVE * k))
    ecc_rod = ecc_rod_mesh.to_object("eccentric_rod", parent=root, location=tuple(v0), semantic_part="valve_gear")
    sp = vx.MeshBuilder()
    sp.prism(0.03 * k, -0.9 * k, 0.0, "steel", sides=8, center=(0.0, 0.0), axis="X")               # valve spindle
    spindle = sp.to_object("valve_spindle", parent=root, location=tuple(v0), semantic_part="valve_gear")

    def rod_angle(t: float) -> float:
        e, vx_ = ecc(t), valve_x(t)
        return math.atan2(-(e.z - Z_VALVE * k), e.x - vx_)

    def conrod_angle(t: float) -> float:
        p = pin(t)
        return math.atan2(-(p.z - zk), p.x - crosshead_x(t))

    conrod.rotation_euler[1] = conrod_angle(0.0)
    ecc_rod.rotation_euler[1] = rod_angle(0.0)

    # ------------------------------------------------------------------ Watt governor on the valve chest
    gx, gy, gz = -1.8 * k, 0.24 * k, zk + 0.72 * k
    gb = vx.MeshBuilder()
    gb.prism(0.06 * k, gz, gz + 0.1 * k, accent, sides=8, center=(gx, gy))
    root_gov = gb.to_object("governor_base", parent=root, semantic_part="governor")
    head = vx.MeshBuilder()
    h = 0.62 * k
    head.prism(0.025 * k, 0.0, h, "steel", sides=8)
    head.prism(0.05 * k, h, h + 0.06 * k, "brass", sides=8)
    head.prism(0.05 * k, h * 0.45, h * 0.55, "brass", sides=8)                                     # sleeve
    for s in (-1, 1):
        ball = Vector((s * 0.26 * k, 0.0, h * 0.42))
        head.strut((0.0, 0.0, h), tuple(ball), 0.025 * k, "steel", depth=0.025 * k)
        head.strut((0.0, 0.0, h * 0.5), tuple((ball + Vector((0.0, 0.0, h))) / 2), 0.02 * k, "steel", depth=0.02 * k)
        head.sphere(tuple(ball), 0.08 * k, "brass", rings=4, sides=8)
    governor = head.to_object("governor", parent=root_gov, location=(gx, gy, gz + 0.1 * k), semantic_part="governor")

    if vx.level() >= 3:
        vx.spin_animation(crank, "crank", axis=1, turns=-turns)
        vx.periodic_animation(slider, "location", 0, crosshead_x, step=1)
        vx.periodic_animation(conrod, "location", 0, crosshead_x, step=1)
        vx.periodic_animation(conrod, "rotation_euler", 1, conrod_angle, step=1)
        vx.periodic_animation(ecc_rod, "location", 0, valve_x, step=1)
        vx.periodic_animation(ecc_rod, "rotation_euler", 1, rod_angle, step=1)
        vx.periodic_animation(spindle, "location", 0, valve_x, step=1)
        vx.spin_animation(governor, "governor", axis=2, turns=3 * turns)
        if params["particles"]:
            puffs = 2 * turns                                         # double acting: exhaust at each dead centre
            vx.particles(root, "exhaust", (-2.3 * k, 0.3 * k, 2.72 * k), count=10, colors=("plaster", "stone", "steel"),
                         velocity=(0.25 * k, -0.15 * k, 1.1 * k), spread=0.25 * k, size=0.22 * k, cycles=puffs,
                         life=0.9, profile="puff", burst=True, phase=0.02, seed=5)
            for x, seed in ((X_BACK + 0.25, 8), (X_FRONT - 0.25, 9)):  # drain cocks under the cylinder
                vx.particles(root, f"drain_{seed}", (x * k, -0.3 * k, zk - 0.42 * k), count=5,
                             colors=("plaster", "steel"), velocity=(0.0, -0.55 * k, 0.12 * k), spread=0.1 * k,
                             size=0.12 * k, cycles=puffs, life=0.6, profile="puff", burst=True,
                             phase=0.0 if seed == 8 else 0.5 / puffs, seed=seed)
    return root
