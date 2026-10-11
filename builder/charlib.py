"""Character kit (runs inside Blender): the humanoid_v1 Armature, low-poly toon body parts skinned to it
and the shared animation set as named actions in NLA tracks (one glTF clip per track).

Two body sources, one rig and one clip set:
- `body_template: procedural` — the V1 kit below: a big boxy head with a wide flat face, a faceted hair
  shell with angular bangs, face plates, segmented limbs, oversized hands and shoes, clothes as colour
  blocks;
- `body_template: <id>` — Character Factory V2 (`build_template_body`): an authored low-poly template
  (builder/character_templates/body/<id>) deformed to the params by builder/chartemplate.py, dressed in
  garment shells, hair and face decals from builder/charwear.py; the skeleton comes from the deformed
  proportions and the template weights skin it.
Every vertex is weighted to one or two bones (joint rings blend 50/50).
Changing this file (or humanoid / chartemplate / charwear) changes every character: bump their
generator_version."""

from __future__ import annotations

import math
from typing import Any, Callable

import bpy
from mathutils import Quaternion, Vector

import humanoid as hu
import voxlib as vx

FRONT = Vector((0.0, -1.0, 0.0))
Weights = dict[str, float]


def _frame(direction: Vector) -> tuple[Vector, Vector]:
    """Lateral (u) and front-facing (v) axes of a ring around `direction`."""
    d = direction.normalized()
    u = d.cross(FRONT)
    if u.length < 1e-6:
        u = Vector((1.0, 0.0, 0.0))
    u.normalize()
    return u, u.cross(d)


def box8(c: Vector, hx: float, hy: float, hz: float) -> list[Vector]:
    """Corners of an axis-aligned box: 0–3 bottom, 4–7 top."""
    return [c + Vector((sx * hx, sy * hy, sz * hz)) for sz in (-1, 1)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


class SkinMesh:
    """Vertices with bone weights and palette-coloured faces, turned into one skinned mesh object."""

    def __init__(self, name: str, *, outline: bool = True) -> None:
        self.name, self.outline = name, outline
        self.verts: list[Vector] = []
        self.weights: list[Weights] = []
        self.faces: list[tuple[list[int], str]] = []

    def vert(self, co: Vector, w: Weights) -> int:
        self.verts.append(Vector(co))
        self.weights.append(dict(w))
        return len(self.verts) - 1

    def face(self, idx: list[int], color: str, inside: Vector) -> None:
        pts = [self.verts[i] for i in idx]
        n = Vector()
        for i, p in enumerate(pts):                                  # Newell normal
            q = pts[(i + 1) % len(pts)]
            n += Vector(((p.y - q.y) * (p.z + q.z), (p.z - q.z) * (p.x + q.x), (p.x - q.x) * (p.y + q.y)))
        centre = sum(pts, Vector()) / len(pts)
        self.faces.append((idx if n.dot(centre - inside) >= 0 else list(reversed(idx)), color))

    # -- rings and lofts
    def ring(self, points: list[Vector], w: Weights | Callable[[Vector], Weights]) -> list[int]:
        return [self.vert(p, w(p) if callable(w) else w) for p in points]

    def loft(self, rings: list[list[int]], colors: list[str], *, cap0: bool = True, cap1: bool = True) -> None:
        centres = [sum((self.verts[i] for i in r), Vector()) / len(r) for r in rings]
        for k in range(len(rings) - 1):
            a, b = rings[k], rings[k + 1]
            inside = (centres[k] + centres[k + 1]) / 2
            for i in range(len(a)):
                j = (i + 1) % len(a)
                self.face([a[i], a[j], b[j], b[i]], colors[min(k, len(colors) - 1)], inside)
        if cap0:
            self.face(list(rings[0]), colors[0], centres[1])
        if cap1:
            self.face(list(rings[-1]), colors[-1], centres[-2])

    def hexa(self, corners: list[Vector], color: str, w: Weights) -> None:
        idx = [self.vert(c, w) for c in corners]
        inside = sum(corners, Vector()) / 8
        for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.face([idx[i] for i in f], color, inside)

    def plate(self, outline: list[Vector], normal: Vector, thickness: float, color: str, w: Weights,
              offset: float = 0.0) -> None:
        """A flat polygon lifted `offset` off its host plane, `thickness` thick (eyes, bangs, bibs)."""
        n = normal.normalized()
        base = [p + n * offset for p in outline]
        top = [p + n * (offset + thickness) for p in outline]
        idx0 = [self.vert(p, w) for p in base]
        idx1 = [self.vert(p, w) for p in top]
        inside = sum(base, Vector()) / len(base) + n * (thickness / 2)
        self.face(idx1, color, inside)
        self.face(idx0, color, inside)
        m = len(outline)
        for i in range(m):
            j = (i + 1) % m
            self.face([idx0[i], idx0[j], idx1[j], idx1[i]], color, inside)

    def to_object(self, armature: bpy.types.Object) -> bpy.types.Object | None:
        if not self.faces:
            return None
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata([tuple(v) for v in self.verts], [], [f for f, _c in self.faces])
        mesh.update()
        loop_colors: list[float] = []
        for poly, (_idx, color) in zip(mesh.polygons, self.faces):
            rgba = vx.CTX.palette[color]
            for _li in poly.loop_indices:
                loop_colors.extend(rgba)
        col = mesh.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
        col.data.foreach_set("color_srgb", loop_colors)
        mesh.color_attributes.active_color = col
        mesh.color_attributes.render_color_index = 0
        mesh.materials.append(vx.palette_material())
        obj = bpy.data.objects.new(self.name, mesh)
        vx.link(obj)
        groups: dict[str, bpy.types.VertexGroup] = {}
        for i, w in enumerate(self.weights):
            total = sum(w.values()) or 1.0
            for bone, value in w.items():
                if value <= 0:
                    continue
                group = groups.get(bone) or obj.vertex_groups.new(name=bone)
                groups[bone] = group
                group.add([i], value / total, "REPLACE")
        obj.parent = armature
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = armature
        obj["character_part"] = self.name
        if not self.outline:
            obj["no_outline"] = True
        return obj


# ---------------------------------------------------------------------------------- ring shapes
def box_ring(c: Vector, u: Vector, v: Vector, w: float, df: float, db: float, cf: float = 0.25,
             cb: float = 0.35) -> list[Vector]:
    """Eight points of a chamfered rectangle: a wide flat front (+v, points 7 → 0), chamfered back."""
    return [c + v * df + u * (w * (1 - cf)), c + v * (df * (1 - cf)) + u * w,
            c - v * (db * (1 - cb)) + u * w, c - v * db + u * (w * (1 - cb)),
            c - v * db - u * (w * (1 - cb)), c - v * (db * (1 - cb)) - u * w,
            c + v * (df * (1 - cf)) - u * w, c + v * df - u * (w * (1 - cf))]


def ngon_ring(c: Vector, u: Vector, v: Vector, rx: float, ry: float, sides: int) -> list[Vector]:
    """Regular polygon with a flat face toward +v."""
    return [c + u * (rx * math.cos(a)) + v * (ry * math.sin(a))
            for a in (math.pi / 2 + math.pi / sides + 2 * math.pi * k / sides for k in range(sides))]


def blend(a: str, b: str, t: float = 0.5) -> Weights:
    return {a: 1 - t, b: t}


def _quad_point(q: list[Vector], a: float, bb: float) -> Vector:
    """Bilinear point of a quad (bottom-left, bottom-right, top-right, top-left), a across, bb up."""
    return q[0].lerp(q[1], a).lerp(q[3].lerp(q[2], a), bb)


def _quad_normal(q: list[Vector]) -> Vector:
    """Unit normal of a face quad, turned to the character's front (−Y)."""
    n = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
    return -n if n.y > 0 else n


# ---------------------------------------------------------------------------------- outfits
OUTFITS: dict[str, dict[str, Any]] = {
    # torso/hips/legs: colour keys; sleeve: where the garment ends on the arm (0 shoulder … 1 wrist)
    "worker": {"torso": "secondary", "hips": "primary", "legs": "primary", "sleeve": 0.45, "cuff": None,
               "hands": "gloves", "shoes": "boots", "bib": True, "hem": None, "collar": None},
    "mechanic": {"torso": "primary", "hips": "dark", "legs": "dark", "sleeve": 0.55, "cuff": "secondary",
                 "hands": "skin", "shoes": "boots", "bib": False, "hem": None, "collar": "secondary"},
    "civilian": {"torso": "primary", "hips": "primary", "legs": "tights", "sleeve": 1.0, "cuff": None,
                 "hands": "skin", "shoes": "light", "bib": False, "hem": "primary", "collar": None, "bell": True},
}
FIXED = {"dark": "steel_dark", "tights": "ink", "gloves": "wood", "sole": "ink", "boots": "wood_dark"}


def _palette(params: dict[str, Any]) -> dict[str, str]:
    return {"primary": params["primary_color"], "secondary": params["secondary_color"], "skin": params["skin_color"],
            "hair": params["hair_color"], "eyes": params["eye_color"], **FIXED}


# ---------------------------------------------------------------------------------- body parts
def _legs(body: SkinMesh, b: hu.Body, joints: dict, col: dict[str, str], outfit: dict) -> None:
    H, w = b.height, b.width
    for tag in ("L", "R"):
        hip, knee = Vector(joints[f"thigh.{tag}"][0]), Vector(joints[f"shin.{tag}"][0])
        ankle = Vector(joints[f"foot.{tag}"][0])
        u, v = _frame(Vector((0, 0, -1)))
        specs = [(hip + Vector((0, 0, 0.02 * H)), 0.05 * H * w, blend("pelvis", f"thigh.{tag}", 0.6)),
                 (hip.lerp(knee, 0.45), 0.043 * H * w, {f"thigh.{tag}": 1.0}),
                 (knee, 0.033 * H * w, blend(f"thigh.{tag}", f"shin.{tag}")),
                 (knee.lerp(ankle, 0.35), 0.036 * H * w, {f"shin.{tag}": 1.0}),
                 (ankle + Vector((0, 0, 0.012 * H)), 0.026 * H * w, {f"shin.{tag}": 1.0})]
        rings = [body.ring(ngon_ring(c, u, v, r, r * 0.95, 6), wt) for c, r, wt in specs]
        body.loft(rings, [col[outfit["legs"]]], cap0=False)
        # shoe: an upper tapering to the toe on a wider sole; heel behind the ankle; rigid to the foot
        light = outfit["shoes"] == "light"
        length = b.foot * (1.02 if light else 1.3)
        width = 0.04 * H * (0.92 if light else 1.2)
        top = b.ankle_z * (1.05 if light else 1.6)
        heel, toe = ankle.y + 0.3 * length, ankle.y - 0.7 * length
        x, sole = ankle.x, 0.018 * H
        fw = {f"foot.{tag}": 1.0}
        body.hexa([Vector((x - width, heel, sole)), Vector((x + width, heel, sole)),
                   Vector((x + width * 0.9, toe, sole)), Vector((x - width * 0.9, toe, sole)),
                   Vector((x - width * 0.85, heel - 0.02 * H, top)), Vector((x + width * 0.85, heel - 0.02 * H, top)),
                   Vector((x + width * 0.8, toe + 0.35 * length, top * 0.55)),
                   Vector((x - width * 0.8, toe + 0.35 * length, top * 0.55))],
                  col["secondary"] if light else col["boots"], fw)
        s = 1.08
        body.hexa([Vector((x - width * s, heel + 0.01, 0.0)), Vector((x + width * s, heel + 0.01, 0.0)),
                   Vector((x + width * s, toe - 0.012, 0.0)), Vector((x - width * s, toe - 0.012, 0.0)),
                   Vector((x - width * s, heel + 0.01, sole)), Vector((x + width * s, heel + 0.01, sole)),
                   Vector((x + width * s, toe - 0.012, sole)), Vector((x - width * s, toe - 0.012, sole))],
                  col["sole"], fw)


def _torso(body: SkinMesh, b: hu.Body, col: dict[str, str], outfit: dict) -> None:
    H, w, sw = b.height, b.width, b.shoulder
    u, v = _frame(Vector((0, 0, 1)))

    def c(z: float) -> Vector:
        return Vector((0.0, 0.0, z))

    hips = [(b.hip_z - 0.055 * H, 0.09 * H * w, 0.08 * H * w, {"pelvis": 1.0}),
            (b.hip_z, 0.1 * H * w, 0.088 * H * w, {"pelvis": 1.0}),
            (b.waist_z, 0.086 * H * w, 0.078 * H * w, blend("pelvis", "spine", 0.6))]
    chest = [(b.waist_z, 0.086 * H * w, 0.078 * H * w, blend("pelvis", "spine", 0.6)),
             ((b.waist_z + b.chest_z) / 2, 0.09 * H * w, 0.083 * H * w, {"spine": 1.0}),
             (b.chest_z, 0.104 * H * w * sw ** 0.5, 0.09 * H * w, blend("spine", "chest", 0.7)),
             (b.shoulder_z - 0.025 * H, 0.116 * H * sw * w ** 0.5, 0.084 * H * w, {"chest": 1.0}),
             (b.shoulder_z + 0.006 * H, 0.078 * H * sw, 0.06 * H, blend("chest", "neck", 0.25))]
    body.loft([body.ring(box_ring(c(z), u, v, rx, ry, ry), wt) for z, rx, ry, wt in hips], [col[outfit["hips"]]])
    body.loft([body.ring(box_ring(c(z), u, v, rx, ry, ry), wt) for z, rx, ry, wt in chest], [col[outfit["torso"]]])
    if outfit["bib"]:                                            # overall bib, straps, two brass buttons
        top = b.chest_z + 0.02 * H
        zb, x0, x1 = b.waist_z, 0.062 * H * w, 0.07 * H * w
        yf = -0.078 * H * w
        body.plate([Vector((-x1, yf, zb)), Vector((x1, yf, zb)), Vector((x0, yf, top)), Vector((-x0, yf, top))],
                   FRONT, 0.012, col["primary"], {"spine": 1.0})
        for s in (-1, 1):
            p0 = Vector((s * 0.054 * H, yf - 0.006, top - 0.01))
            p1 = Vector((s * 0.07 * H * sw, 0.0, b.shoulder_z + 0.01 * H))
            p2 = Vector((s * 0.06 * H, 0.085 * H * w, b.waist_z + 0.04 * H))
            for a, bb in ((p0, p1), (p1, p2)):
                uu, vv = _frame(bb - a)
                body.loft([body.ring(ngon_ring(p, uu, vv, 0.012 * H, 0.006 * H, 4), {"chest": 1.0}) for p in (a, bb)],
                          [col["primary"]])
            body.hexa(box8(Vector((s * 0.054 * H, yf - 0.016, top - 0.012)), 0.011, 0.006, 0.011), "brass",
                      {"chest": 1.0})
    if outfit["hem"]:                                            # a coat flaring over the thighs

        def hem_weights(p: Vector) -> Weights:
            side = "L" if p.x > 0 else "R"
            return {"pelvis": 0.45, f"thigh.{side}": 0.55} if abs(p.x) > 0.01 * H else {"pelvis": 1.0}

        levels = [(b.waist_z, 0.09 * H * w, 0.082 * H * w, {"pelvis": 0.6, "spine": 0.4}),
                  (b.hip_z, 0.108 * H * w, 0.095 * H * w, {"pelvis": 1.0}),
                  (b.hip_z - 0.12 * H, 0.135 * H * w, 0.115 * H * w, hem_weights)]
        rings = [body.ring(box_ring(c(z), u, v, rx, ry, ry, 0.3, 0.3), wt) for z, rx, ry, wt in levels]
        body.loft(rings, [col[outfit["hem"]]], cap0=False, cap1=False)
    if outfit.get("collar"):
        rings = [body.ring(ngon_ring(c(z), u, v, r, r * 0.9, 8), blend("chest", "neck", 0.3))
                 for z, r in ((b.shoulder_z - 0.004 * H, 0.06 * H * sw), (b.shoulder_z + 0.032 * H, 0.05 * H))]
        body.loft(rings, [col[outfit["collar"]]])


def _arms(body: SkinMesh, b: hu.Body, joints: dict, col: dict[str, str], outfit: dict, hand_scale: float) -> None:
    H, w = b.height, b.width
    for tag in ("L", "R"):
        sh, el = Vector(joints[f"upper_arm.{tag}"][0]), Vector(joints[f"upper_arm.{tag}"][1])
        wr, tip = Vector(joints[f"hand.{tag}"][0]), Vector(joints[f"hand.{tag}"][1])
        d = (wr - sh).normalized()
        u, v = _frame(d)
        up, fore, hand = f"upper_arm.{tag}", f"forearm.{tag}", f"hand.{tag}"
        bell = 1.9 if outfit.get("bell") else 1.0
        specs = [(sh - d * 0.02 * H, 0.04 * H * w, blend("chest", up, 0.7), 0.0),
                 (sh.lerp(el, 0.5), 0.033 * H * w, {up: 1.0}, 0.25),
                 (el, 0.027 * H * w, blend(up, fore), 0.5),
                 (el.lerp(wr, 0.5), 0.028 * H * w, {fore: 1.0}, 0.75),
                 (wr - d * 0.004 * H, 0.023 * H * w * bell, {fore: 1.0}, 1.0)]
        rings = [body.ring(ngon_ring(c, u, v, r, r, 6), wt) for c, r, wt, _t in specs]
        sleeve = outfit["sleeve"]
        colors = [col[outfit["torso"]] if (specs[k][3] + specs[k + 1][3]) / 2 < sleeve else col["skin"]
                  for k in range(len(specs) - 1)]
        body.loft(rings, colors)
        if outfit.get("cuff"):                                  # a rolled sleeve band at the sleeve end
            at = sh.lerp(wr, sleeve)
            wt = blend(up, fore, 0.5) if abs(sleeve - 0.5) < 0.1 else {fore if sleeve > 0.5 else up: 1.0}
            band = [body.ring(ngon_ring(at + d * dd, u, v, 0.037 * H * w, 0.037 * H * w, 6), wt)
                    for dd in (-0.022 * H, 0.022 * H)]
            body.loft(band, [col[outfit["cuff"]]])
        cap = [body.ring(ngon_ring(sh + Vector((0, 0, 0.004 * H)) + d * dd, u, v, 0.046 * H * w, 0.044 * H * w, 6),
                         blend("chest", up, 0.6)) for dd in (-0.03 * H, 0.03 * H)]          # shoulder cap
        body.loft(cap, [col[outfit["torso"]]])
        # mitten hand: palm block + thumb, oversized, rigid to the hand bone
        hw_, ht, hl = 0.036 * H * hand_scale, 0.021 * H * hand_scale, b.hand * hand_scale
        hc = col["gloves"] if outfit["hands"] == "gloves" else col["skin"]
        hd = (tip - wr).normalized()
        hu_, hv = _frame(hd)
        base, end = wr - hd * 0.006, wr + hd * hl
        corners = [base + hu_ * sx * hw_ * 0.8 + hv * sy * ht for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        corners += [end + hu_ * sx * hw_ + hv * sy * ht * 0.8 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        body.hexa(corners, hc, {hand: 1.0})
        tb = wr + hd * hl * 0.25 + hv * ht * 0.6
        te = tb + (hv * 0.8 + hd * 0.6).normalized() * hl * 0.45
        tu, tv = _frame(te - tb)
        body.loft([body.ring(ngon_ring(p, tu, tv, ht * 0.55, ht * 0.5, 4), {hand: 1.0}) for p in (tb, te)], [hc])


def _head(body: SkinMesh, b: hu.Body, col: dict[str, str]) -> dict[str, Any]:
    """Neck and a boxy head with a wide flat face; returns the face quads for features and hair."""
    H, hh = b.height, b.head_h
    u, v = _frame(Vector((0, 0, 1)))
    neck = [body.ring(ngon_ring(Vector((0, 0, z)), u, v, r, r, 6), wt) for z, r, wt in (
        (b.shoulder_z - 0.01 * H, 0.03 * H, blend("chest", "neck", 0.6)),
        (b.chin_z + 0.02 * H, 0.028 * H, blend("neck", "head", 0.7)))]
    body.loft(neck, [col["skin"]])
    hw, hd = hh * 0.5, hh * 0.44
    z0 = b.chin_z - 0.01 * H
    levels = [(0.0, 0.45, 0.5, 0.6), (0.17, 0.84, 0.9, 0.3), (0.36, 1.0, 1.0, 0.18), (0.78, 1.0, 1.0, 0.18),
              (1.0, 0.84, 0.86, 0.35)]
    rings = [body.ring(box_ring(Vector((0, -0.08 * hd, z0 + f * hh)), u, v, hw * sx, hd * sy, hd * sy, cf, 0.4),
                       {"head": 1.0}) for f, sx, sy, cf in levels]
    body.loft(rings, [col["skin"]])

    def quad(lo: list[int], hi: list[int]) -> list[Vector]:                        # bl, br, tr, tl
        return [body.verts[lo[7]], body.verts[lo[0]], body.verts[hi[0]], body.verts[hi[7]]]
    return {"face": quad(rings[2], rings[3]), "lower": quad(rings[1], rings[2]), "hw": hw, "hd": hd, "z0": z0,
            "hh": hh}


EXPRESSIONS = {   # inner-brow drop (fraction), brow lift, mouth shape — the hook for a later facial layer
    "neutral": (0.0, 0.0, "line"), "happy": (-0.1, 0.08, "smile"), "angry": (0.35, -0.05, "frown"),
    "sad": (-0.35, 0.02, "frown"), "scared": (-0.3, 0.2, "open"),
}


def _face(face: SkinMesh, head: dict[str, Any], col: dict[str, str], expression: str) -> None:
    q, lower = head["face"], head["lower"]
    n = _quad_normal(q)
    w = {"head": 1.0}
    drop, lift, mouth = EXPRESSIONS.get(expression, EXPRESSIONS["neutral"])

    def poly(cx: float, cy: float, rx: float, ry: float, sides: int, rot: float = 0.0) -> list[Vector]:
        return [_quad_point(q, cx + rx * math.cos(rot + 2 * math.pi * k / sides),
                            cy + ry * math.sin(rot + 2 * math.pi * k / sides)) for k in range(sides)]

    brow_lift = 0.04 + 0.012 + 0.02 * head["hh"] + 0.004       # in front of the bangs, anime-style
    for side in (-1, 1):
        cx = 0.5 + side * 0.25
        face.plate(poly(cx, 0.44, 0.19, 0.4, 6, math.pi / 2), n, 0.003, "white", w, offset=0.002)        # sclera
        face.plate(poly(cx - side * 0.02, 0.4, 0.13, 0.3, 6, math.pi / 2), n, 0.003, col["eyes"], w, offset=0.005)
        face.plate(poly(cx - side * 0.02, 0.38, 0.06, 0.145, 6, math.pi / 2), n, 0.003, "ink", w, offset=0.008)
        face.plate(poly(cx - side * 0.07, 0.53, 0.04, 0.08, 4), n, 0.002, "white", w, offset=0.011)    # highlight
        lash = [(cx - 0.21, 0.76), (cx + 0.21, 0.79), (cx + 0.21 + side * 0.06, 0.93), (cx - 0.19, 0.87)]
        face.plate([_quad_point(q, a, bb) for a, bb in lash], n, 0.003, "ink", w, offset=0.009)
        inner, outer = cx - side * 0.15, cx + side * 0.15
        y_in, y_out = 0.95 + lift - drop * 0.3, 0.95 + lift
        brow = [(inner, y_in), (outer, y_out), (outer, y_out + 0.07), (inner, y_in + 0.07)]
        face.plate([_quad_point(q, a, bb) for a, bb in brow], n, 0.004, col["hair"], w, offset=brow_lift)
    shapes = {"line": [(0.41, 0.5), (0.59, 0.5), (0.58, 0.6), (0.42, 0.6)],
              "smile": [(0.36, 0.72), (0.64, 0.72), (0.57, 0.42), (0.43, 0.42)],
              "frown": [(0.38, 0.42), (0.62, 0.42), (0.56, 0.56), (0.44, 0.56)],
              "open": [(0.43, 0.3), (0.57, 0.3), (0.6, 0.66), (0.4, 0.66)]}
    face.plate([_quad_point(lower, a, bb) for a, bb in shapes[mouth]], _quad_normal(lower), 0.003, "ink", w,
               offset=0.003)


def _hair(hair: SkinMesh, b: hu.Body, head: dict[str, Any], col: dict[str, str], style: str) -> None:
    if style == "bald":
        return
    hh, hw, hd, z0 = b.head_h, head["hw"], head["hd"], head["z0"]
    u, v = _frame(Vector((0, 0, 1)))
    hc, w = col["hair"], {"head": 1.0}
    grow = 1.17 if style != "bob" else 1.22
    centre_y = -0.08 * hd
    # hem heights (fraction of the head) per ring point: front · front sides · back sides · back
    hem = {"short": (0.8, 0.62, 0.5, 0.42), "messy": (0.8, 0.58, 0.45, 0.38), "bob": (0.8, 0.3, 0.18, 0.2)}[style]
    hem_z = [hem[0], hem[1], hem[2], hem[3], hem[3], hem[2], hem[1], hem[0]]
    flare = 1.18 if style == "bob" else 1.0
    base = box_ring(Vector((0, centre_y, 0)), u, v, hw * grow, hd * grow, hd * grow * 1.05, 0.2, 0.4)
    ring0 = hair.ring([Vector((p.x * (flare if i not in (0, 7) else 1.0), p.y, z0 + hem_z[i] * hh))
                       for i, p in enumerate(base)], w)
    mid = box_ring(Vector((0, centre_y, z0 + 0.86 * hh)), u, v, hw * grow * 1.02, hd * grow, hd * grow * 1.04, 0.2, 0.4)
    top = box_ring(Vector((0, centre_y + 0.02 * hd, z0 + 1.12 * hh)), u, v, hw * grow * 0.74, hd * grow * 0.74,
                   hd * grow * 0.78, 0.3, 0.4)
    hair.loft([ring0, hair.ring(mid, w), hair.ring(top, w)], [hc], cap0=False)
    hem_pts = [hair.verts[i] for i in ring0]
    teeth = {"short": 2, "messy": 3, "bob": 3}[style]
    depth = {"short": 0.1, "messy": 0.16, "bob": 0.2}[style] * hh
    for i in range(1, 7):                                         # sides and back, never over the face
        a, bpt = hem_pts[i], hem_pts[i + 1]
        normal = ((a + bpt) / 2 - Vector((0, centre_y, (a.z + bpt.z) / 2)))
        normal.z = 0.0
        for k in range(teeth):
            p0, p1 = a.lerp(bpt, k / teeth), a.lerp(bpt, (k + 1) / teeth)
            tip = p0.lerp(p1, 0.5 + (0.15 if k % 2 else -0.15)) + Vector((0, 0, -depth * (0.7 + 0.3 * (k % 2))))
            hair.plate([p0, p1, tip], normal, 0.018 * hh, hc, w, offset=-0.009 * hh)
    # angular bangs hanging from the hairline over the brow, in front of the face plane
    q = head["face"]
    n = _quad_normal(q)
    count = 6 if style == "messy" else 5
    for k in range(count):
        a0, a1 = -0.08 + k * 1.16 / count, -0.08 + (k + 1) * 1.16 / count
        tip = ((a0 + a1) / 2 + (0.06 if k % 2 else -0.04), 0.9 - 0.07 * (k % 2) - (0.05 if style == "bob" else 0.0))
        pts = [_quad_point(q, a0, 1.3), _quad_point(q, a1, 1.3), _quad_point(q, *tip)]
        hair.plate(pts, n, 0.02 * hh, hc, w, offset=0.04)
    for side in (-1, 1):                                          # side locks: spikes from the side hem
        root_z = z0 + (hem[1] + 0.05) * hh
        length = {"short": 0.3, "messy": 0.35, "bob": 0.36}[style] * hh
        x = side * hw * grow * flare
        for dy in ((-0.45, 0.0) if style != "bob" else (-0.55, -0.1, 0.35)):
            y = centre_y + dy * hd
            pts = [Vector((x, y - 0.12 * hd, root_z)), Vector((x, y + 0.12 * hd, root_z)),
                   Vector((x - side * 0.1 * hw, y + 0.02 * hd, root_z - length))]
            hair.plate(pts, Vector((side, 0, 0)), 0.02 * hh, hc, w, offset=-0.01)
    if style == "messy":                                          # spikes sticking out of the crown
        for ax, ay in ((0.0, 0.3), (0.55, 0.1), (-0.55, 0.15), (0.3, 0.7), (-0.35, 0.65)):
            c = Vector((ax * hw, centre_y + ay * hd, z0 + 1.02 * hh))
            out = Vector((ax * 0.6, ay * 0.5, 1.0)).normalized()
            uu, vv = _frame(out)
            hair.loft([hair.ring(ngon_ring(c, uu, vv, 0.14 * hw, 0.1 * hw, 4), w),
                       hair.ring(ngon_ring(c + out * 0.22 * hh, uu, vv, 0.01, 0.01, 4), w)], [hc])


def _goggles(gear: SkinMesh, b: hu.Body, head: dict[str, Any]) -> None:
    hh, hw, hd, z0 = b.head_h, head["hw"], head["hd"], head["z0"]
    u, v = _frame(Vector((0, 0, 1)))
    z = z0 + 0.95 * hh
    band = [gear.ring(box_ring(Vector((0, -0.08 * hd, z + dz)), u, v, hw * 1.2, hd * 1.18, hd * 1.2, 0.2, 0.4),
                      {"head": 1.0}) for dz in (-0.035 * hh, 0.035 * hh)]
    gear.loft(band, ["ink"], cap0=False, cap1=False)
    y = -0.08 * hd - hd * 1.22
    uu, vv = Vector((1, 0, 0)), Vector((0, 0, 1))
    for side in (-1, 1):
        c = Vector((side * 0.42 * hw, y, z + 0.02 * hh))

        def disc(r: float, dy: float) -> list[Vector]:
            return [c + Vector((0, dy, 0)) + uu * (r * math.cos(a)) + vv * (r * math.sin(a))
                    for a in (2 * math.pi * k / 8 + math.pi / 8 for k in range(8))]
        gear.loft([gear.ring(disc(0.3 * hw, dy), {"head": 1.0}) for dy in (0.05 * hd, -0.08 * hd)], ["brass"])
        gear.plate(disc(0.22 * hw, -0.085 * hd), FRONT, 0.004, "glass", {"head": 1.0})


def _scarf(gear: SkinMesh, b: hu.Body, col: dict[str, str]) -> None:
    H = b.height
    u, v = _frame(Vector((0, 0, 1)))
    rings = [gear.ring(box_ring(Vector((0, 0, z)), u, v, r, r * 0.9, r * 0.9, 0.35, 0.35), blend("chest", "neck", t))
             for z, r, t in ((b.shoulder_z - 0.012 * H, 0.056 * H, 0.2), (b.shoulder_z + 0.018 * H, 0.05 * H, 0.5),
                             (b.shoulder_z + 0.04 * H, 0.04 * H, 0.8))]
    gear.loft(rings, [col["secondary"]])
    tail_top = Vector((0.03 * H, -0.07 * H, b.shoulder_z - 0.012 * H))
    gear.hexa(box8(tail_top + Vector((0.006 * H, -0.004 * H, -0.05 * H)), 0.014 * H, 0.006 * H, 0.05 * H),
              col["secondary"], {"chest": 1.0})


# ---------------------------------------------------------------------------------- armature and clips
def armature(b: hu.Body) -> tuple[bpy.types.Object, dict]:
    joints = hu.skeleton(b)
    data = bpy.data.armatures.new(hu.RIG)
    arm = bpy.data.objects.new("rig", data)
    vx.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, connected in hu.BONES:
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = joints[name]
        if parent:
            bone.parent = data.edit_bones[parent]
            bone.use_connect = connected
    bpy.ops.object.mode_set(mode="OBJECT")
    arm["rig"] = hu.RIG
    data.display_type = "STICK"
    return arm, joints


def animate(arm: bpy.types.Object, b: hu.Body, joints: dict) -> list[str]:
    """Each clip of the shared set as its own action in an NLA track of the same name."""
    arm.animation_data_create()
    rest = {pb.name: pb.bone.matrix_local.to_quaternion() for pb in arm.pose.bones}
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    made = []
    for clip, frames in hu.CLIPS.items():
        action = bpy.data.actions.new(clip)
        arm.animation_data.action = action
        for f in range(frames + 1):
            ch = hu.pose(clip, b, f)
            rots = hu.rotations(joints, ch)
            for pb in arm.pose.bones:
                q = Quaternion()
                for axis, angle in rots.get(pb.name, []):
                    q = Quaternion(Vector(axis), angle) @ q
                m = rest[pb.name]
                pb.rotation_quaternion = m.inverted() @ q @ m
                pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
            pel = arm.pose.bones["pelvis"]
            pel.location = rest["pelvis"].inverted() @ Vector(hu.pelvis_offset(ch))
            pel.keyframe_insert("location", frame=f, group="pelvis")
        for fc in vx.iter_fcurves(action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        track = arm.animation_data.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 0, action)
        arm.animation_data.action = None
        made.append(clip)
    for pb in arm.pose.bones:                                      # back to the rest pose
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    return made


def part_object(part: Any, armature: bpy.types.Object) -> bpy.types.Object | None:
    """A charwear.Part (pure-Python geometry) as a skinned, palette-coloured mesh object."""
    mesh = SkinMesh(part.name, outline=part.outline)
    mesh.verts = [Vector(v) for v in part.verts]
    mesh.weights = [dict(w) for w in part.weights]
    mesh.faces = list(zip(part.faces, part.colors))
    return mesh.to_object(armature)


def build_template_body(params: dict[str, Any]) -> bpy.types.Object:
    """Character Factory V2: template → morphs → proportions → humanoid_v1 skeleton → deformed mesh,
    garment shells, hair, face decals, accessories; clips as in V1."""
    import chartemplate as ct
    import charwear as cw

    p = dict(params)
    if p.get("hair") == "bob" and p.get("ear_style", "human") != "pointed":
        p["ear_style"] = "small"                                     # the bob covers the ears
    res = ct.build_body(p)
    arm, joints = armature(res.body)
    col = {**_palette(p), "light": p["secondary_color"]}
    outfit, hidden, stats = cw.dress(res, cw.outfit_garments(p), col, p)
    hf = cw.head_frame(res)
    parts = [cw.body_part(res, hidden, col), outfit, cw.face_features(res, p, col, hf), cw.hair(res, p, col, hf)]
    accessory = p.get("accessory", "none")
    if accessory == "goggles":
        parts.append(cw.goggles(res, p, hf))
    elif accessory == "scarf":
        parts.append(cw.scarf(res, col))
    for part in parts:
        if part.faces:
            part_object(part, arm)
    arm["body_template"] = res.template.id
    arm["template_digest"] = res.template.digest
    arm["garments"] = ",".join(stats)
    if vx.level() >= 3:
        animate(arm, res.body, joints)
    return arm


def build(params: dict[str, Any]) -> bpy.types.Object:
    """The whole character: an armature root with skinned body, face, hair and gear meshes."""
    if params.get("body_template", "procedural") != "procedural":
        return build_template_body(params)
    b = hu.body(params)
    arm, joints = armature(b)
    outfit = OUTFITS[params["outfit"]]
    col = _palette(params)
    meshes = {name: SkinMesh(name, outline=name != "face") for name in ("body", "face", "hair", "gear")}
    _legs(meshes["body"], b, joints, col, outfit)
    _torso(meshes["body"], b, col, outfit)
    _arms(meshes["body"], b, joints, col, outfit, float(params.get("hand_scale", 1.0)))
    head = _head(meshes["body"], b, col)
    _face(meshes["face"], head, col, params.get("expression", "neutral"))
    _hair(meshes["hair"], b, head, col, params["hair"])
    accessory = params.get("accessory", "none")
    if accessory == "goggles":
        _goggles(meshes["gear"], b, head)
    elif accessory == "scarf":
        _scarf(meshes["gear"], b, col)
    for mesh in meshes.values():
        mesh.to_object(arm)
    if vx.level() >= 3:
        animate(arm, b, joints)
    return arm
