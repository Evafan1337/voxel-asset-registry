"""Character wear (pure Python): a deformed template body as a mesh, garments as shells over it, hair,
face features and accessories — vertices with humanoid_v1 bone weights and palette-coloured faces.

builder/charlib.py turns every Part into one skinned mesh object; tests read it without Blender.

- **Garments** are shells over the body faces they cover. Coverage is a range of the chain coordinate
  `u` (template: arm shoulder 0 · elbow 1 · wrist 2; leg hip 0 · knee 1 · ankle 2; torso hip 0 · waist 1 ·
  chest 2 · neck 3), so every garment end sits on an edge loop of the template. A shell vertex is its body
  vertex pushed along the body normal and keeps the body weights: the cloth moves exactly with the skin.
  Covered body faces are dropped (nothing can poke through), a garment under a higher layer loses the
  faces the higher one covers, and every open garment end gets a wall down to the body (no gaps).
- **Hair** is sampled from the head surface on a sphere of rays (azimuth × elevation) and pushed out;
  the hem height per azimuth is the style. **Face features** are decals raycast onto the face planes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import chartemplate as ct
from chartemplate import Vec, Weights, add, cross, dot, length, lerp, mul, sub, unit

FACE = ct.FACE_REGIONS


# ---------------------------------------------------------------------------------- parts
@dataclass
class Part:
    """One future mesh object: vertices with bone weights, faces with palette colour names."""

    name: str
    outline: bool = True
    verts: list[Vec] = field(default_factory=list)
    weights: list[Weights] = field(default_factory=list)
    faces: list[list[int]] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)

    def vert(self, p: Vec, w: Weights) -> int:
        self.verts.append(tuple(p))
        self.weights.append(dict(w))
        return len(self.verts) - 1

    def face(self, idx: list[int], color: str, inside: Vec | None = None) -> None:
        """Add a face; with `inside`, flip it so its normal points away from that point."""
        if inside is not None:
            pts = [self.verts[i] for i in idx]
            n = ct.face_normal(self.verts, idx)
            if dot(n, sub(ct.centroid(pts), inside)) < 0:
                idx = list(reversed(idx))
        self.faces.append(list(idx))
        self.colors.append(color)

    def loft(self, rings: list[list[int]], colors: list[str] | str, inside: Callable[[int], Vec],
             cap0: bool = False, cap1: bool = False) -> None:
        cols = [colors] * len(rings) if isinstance(colors, str) else colors
        for k in range(len(rings) - 1):
            a, b = rings[k], rings[k + 1]
            for i in range(len(a)):
                j = (i + 1) % len(a)
                self.face([a[i], a[j], b[j], b[i]], cols[min(k, len(cols) - 1)], inside(k))
        if cap0:
            self.face(list(rings[0]), cols[0], inside(0))
        if cap1:
            self.face(list(rings[-1]), cols[-1], inside(len(rings) - 2))

    @property
    def polys(self) -> int:
        return len(self.faces)


def top2(w: dict[str, float]) -> Weights:
    """At most two influences, normalized (the low-poly rule)."""
    best = sorted(((v, k) for k, v in w.items() if v > 1e-4), reverse=True)[:2]
    total = sum(v for v, _k in best) or 1.0
    return {k: round(v / total, 4) for v, k in best}


def surface_weights(res: ct.BodyResult, fi: int, p: Vec) -> Weights:
    """Bone weights at point `p` on body face `fi` (inverse distance to its vertices, ≤ 2 bones)."""
    acc: dict[str, float] = {}
    for i in res.faces[fi]:
        k = 1.0 / (length(sub(res.verts[i], p)) + 1e-4)
        for b, w in res.weights[i].items():
            acc[b] = acc.get(b, 0.0) + w * k
    return top2(acc)


def nearest_weights(res: ct.BodyResult, p: Vec, ids: list[int] | None = None) -> Weights:
    pool = ids if ids is not None else range(len(res.verts))
    i = min(pool, key=lambda k: length(sub(res.verts[k], p)))
    return dict(res.weights[i])


# ---------------------------------------------------------------------------------- garments
@dataclass(frozen=True)
class Garment:
    id: str
    slot: str                               # top · bottom · shoes · hands
    layer: int                              # higher layers hide the faces of lower ones
    offset: float                           # m off the skin
    cover: dict[str, tuple[float, float]]   # chain kind → u range (whole faces inside)
    color: str                              # colour key (primary, secondary, dark, tights, gloves, boots, light)
    rim_flare: float = 0.0                  # extra offset at the sleeve / trouser ends (cuffs)
    hem_flare: float = 0.002                # extra offset at the torso ends (hem, neckline)
    bulk: tuple[tuple[str, float], ...] = ()   # extra offset per body region (shoulder, chest …)
    cuff: tuple[str, float, str] | None = None  # (chain kind, u width from the end, colour key) band at the ends
    collar: float = 0.0                     # collar height as a fraction of the neck length (0 — none)
    collar_color: str | None = None
    skirt: float = 0.0                      # coat skirt below the torso shell, fraction of the leg
    bell: float = 0.0                       # sleeve flare at the wrist, m
    bib: bool = False                       # overalls: front panel up the chest + straps
    sole: str | None = None                 # shoes: flat sole on z = 0 in this colour key
    toe: float = 0.0                        # boots: toe cap bulk, m
    min_radius: float = 0.0                 # shoes: shaft at least this far from the shin bone (× height)
    placket: str | None = None              # front closure stripe in this colour key (+ buttons for coats)
    buttons: int = 0
    title: str = ""


GARMENTS: dict[str, Garment] = {g.id: g for g in (
    # -- tops
    Garment("tshirt", "top", 3, 0.008, {"torso": (0.25, 3.1), "arm": (-1.0, 0.6)}, "secondary", rim_flare=0.003,
            bulk=(("chest", 0.002),), title="Футболка: короткий рукав до середины плеча"),
    Garment("shirt", "top", 3, 0.011, {"torso": (0.25, 3.1), "arm": (-1.0, 2.05)}, "secondary", rim_flare=0.004,
            collar=0.45, title="Рубашка: длинный рукав, воротник"),
    Garment("jacket", "top", 5, 0.018, {"torso": (-9.0, 3.1), "arm": (-1.0, 1.6), "leg": (-9.0, 0.12)}, "primary",
            rim_flare=0.01, hem_flare=0.0,
            bulk=(("shoulder", 0.008), ("chest", 0.004)), cuff=("arm", 0.28, "secondary"), collar=0.6,
            collar_color="secondary", placket="dark", title="Куртка: рукава закатаны до середины предплечья, контрастные манжеты"),
    Garment("coat", "top", 5, 0.02, {"torso": (-9.0, 3.1), "arm": (-1.0, 2.05), "leg": (-9.0, 0.12)}, "primary",
            rim_flare=0.004, bulk=(("shoulder", 0.006),), skirt=0.34, bell=0.03, collar=0.35, placket="secondary",
            buttons=3,
            title="Пальто: клёш с бёдер до середины бедра, рукав-колокол"),
    Garment("vest", "top", 6, 0.026, {"torso": (0.55, 3.1)}, "secondary", rim_flare=0.004,
            bulk=(("chest", 0.006),), title="Жилет поверх верха"),
    # -- bottoms
    Garment("pants", "bottom", 2, 0.008, {"torso": (-9.0, 1.0), "leg": (-9.0, 2.03)}, "dark", rim_flare=0.004,
            title="Брюки до щиколотки"),
    Garment("work_pants", "bottom", 2, 0.014, {"torso": (-9.0, 1.0), "leg": (-9.0, 2.03)}, "dark", rim_flare=0.01,
            bulk=(("knee", 0.004), ("thigh", 0.003)), title="Рабочие брюки: свободные, с отворотом"),
    Garment("overalls", "bottom", 4, 0.016, {"torso": (-9.0, 1.0), "leg": (-9.0, 2.03)}, "primary", rim_flare=0.01,
            bulk=(("knee", 0.004),), bib=True, title="Комбинезон: нагрудник и лямки поверх футболки"),
    Garment("shorts", "bottom", 2, 0.012, {"torso": (-9.0, 1.0), "leg": (-9.0, 0.5)}, "dark", rim_flare=0.008,
            title="Шорты до середины бедра"),
    Garment("tights", "bottom", 1, 0.004, {"torso": (-9.0, 1.0), "leg": (-9.0, 2.03)}, "tights", title="Колготки"),
    # -- shoes
    Garment("simple", "shoes", 6, 0.009, {"leg": (1.95, 9.0)}, "light", sole="sole", min_radius=0.022,
            title="Лёгкие туфли"),
    Garment("mechanic_boot", "shoes", 6, 0.014, {"leg": (1.6, 9.0)}, "boots", rim_flare=0.008, sole="sole", toe=0.012,
            min_radius=0.03, title="Ботинки механика до середины голени"),
    Garment("worker_boot", "shoes", 6, 0.019, {"leg": (1.35, 9.0)}, "boots", rim_flare=0.012, sole="sole", toe=0.02,
            min_radius=0.036, title="Рабочие сапоги: высокие, тяжёлый носок"),
    # -- hands
    Garment("gloves", "hands", 6, 0.007, {"arm": (1.95, 9.0)}, "gloves", rim_flare=0.008, title="Рабочие перчатки"),
)}

TOPS = ("tshirt", "shirt", "jacket", "coat", "vest")
BOTTOMS = ("pants", "work_pants", "overalls", "shorts", "tights")
SHOES = ("simple", "worker_boot", "mechanic_boot")
# `outfit` presets for template bodies (top / bottom / shoes / hands when those params are "auto")
OUTFIT_SETS: dict[str, dict[str, str | None]] = {
    "worker": {"top": "tshirt", "bottom": "overalls", "shoes": "worker_boot", "hands": "gloves"},
    "mechanic": {"top": "jacket", "bottom": "work_pants", "shoes": "mechanic_boot", "hands": None},
    "civilian": {"top": "coat", "bottom": "tights", "shoes": "simple", "hands": None},
}


def outfit_garments(params: dict[str, Any]) -> list[Garment]:
    base = OUTFIT_SETS[params.get("outfit", "worker")]
    picked = []
    for slot in ("top", "bottom", "shoes", "hands"):
        value = params.get(slot, "auto")
        gid = base.get(slot) if value in (None, "auto") else (None if value == "none" else value)
        if gid:
            picked.append(GARMENTS[gid])
    return sorted(picked, key=lambda g: g.layer)


def covered(res: ct.BodyResult, g: Garment) -> set[int]:
    t = res.template

    def inside(i: int) -> bool:
        rng = g.cover.get(t.chains[i].split(".")[0])
        return rng is not None and rng[0] <= t.u[i] <= rng[1]

    faces = {fi for fi, f in enumerate(t.faces) if all(inside(i) for i in f)}
    if g.bib:                                    # overalls: the front of the torso up to the chest
        for fi, f in enumerate(t.faces):
            if fi in faces or any(t.chains[i] != "torso" for i in f):
                continue
            n = unit(ct.face_normal(res.verts, f))
            u = sum(t.u[i] for i in f) / len(f)
            ax = max(abs(res.verts[i][0]) for i in f)
            if n[1] < -0.35 and 0.9 <= u <= 2.45 and ax < 0.62 * res.body.shoulder_x:
                faces.add(fi)
    return faces


def _boundary(faces: list[list[int]], ids: set[int]) -> list[tuple[int, int, int]]:
    """Directed boundary edges (a → b as wound in the face) of a face set: (a, b, face)."""
    count: dict[tuple[int, int], int] = {}
    for fi in ids:
        f = faces[fi]
        for k in range(len(f)):
            e = tuple(sorted((f[k], f[(k + 1) % len(f)])))
            count[e] = count.get(e, 0) + 1
    out = []
    for fi in ids:
        f = faces[fi]
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            if count[tuple(sorted((a, b)))] == 1:
                out.append((a, b, fi))
    return out


def dress(res: ct.BodyResult, garments: list[Garment], col: dict[str, str], params: dict[str, Any] | None = None
          ) -> tuple[Part, set[int], dict[str, Any]]:
    """Garment shells in one Part; returns it, the body faces they hide and per-garment stats.
    `cloth_bulk` scales every offset off the skin, `sleeve_width` widens the sleeves of the top."""
    t = res.template
    cloth_bulk = float((params or {}).get("cloth_bulk", 1.0))
    sleeve_width = float((params or {}).get("sleeve_width", 1.0))
    part = Part("outfit")
    cover = {g.id: covered(res, g) for g in garments}
    hidden: set[int] = set().union(*cover.values()) if cover else set()
    stats: dict[str, Any] = {}
    for gi, g in enumerate(garments):
        mine = cover[g.id]
        above = set().union(*(cover[h.id] for h in garments[gi + 1:] if h.layer > g.layer)) if gi + 1 < len(garments) else set()
        rim = _boundary(t.faces, mine)
        rim_verts = {a for a, _b, _f in rim} | {b for _a, b, _f in rim}
        bulk = dict(g.bulk)
        base_color = col[g.color]
        cuff_ids: set[int] = set()
        if g.cuff:                                  # the last band of faces at the garment end of that chain
            kind, _width, _c = g.cuff
            ends = {i for i in rim_verts if t.chains[i].startswith(kind)}
            far = max((t.u[i] for i in ends), default=0.0)
            cuff_ids = {fi for fi in mine if any(i in ends and t.u[i] > far - 0.1 for i in t.faces[fi])
                        and all(t.chains[i].startswith(kind) for i in t.faces[fi])}
        shell: dict[int, int] = {}
        inner: dict[int, int] = {}

        def out_vert(i: int) -> int:
            if i not in shell:
                off = (g.offset + bulk.get(ct.region_base(t.regions[i]), 0.0)) * cloth_bulk
                if t.chains[i].startswith("arm") and g.slot == "top":
                    off += (sleeve_width - 1.0) * 0.02
                if i in rim_verts:
                    off += g.hem_flare if t.chains[i] == "torso" else g.rim_flare
                    if g.bell and t.chains[i].startswith("arm") and t.u[i] > 1.8:
                        off += g.bell
                elif g.bell and t.chains[i].startswith("arm") and 1.4 < t.u[i] < 1.8:
                    off += g.bell * 0.35
                n = res.normals[i]
                p = add(res.verts[i], mul(n, off))
                if g.min_radius and t.chains[i].startswith("leg"):
                    p = _widen(res, t.chains[i][-1], p, g.min_radius * res.body.height)
                if g.toe and res.verts[i][1] < res.joints[f"foot.{t.chains[i][-1]}"][0][1] - 0.02:
                    p = add(p, mul(unit((n[0], n[1] - 0.6, 0.0)), g.toe))
                if g.sole and res.verts[i][2] < 0.02:
                    p = (p[0] + n[0] * 0.006, p[1] + n[1] * 0.006, 0.0)
                shell[i] = part.vert((p[0], p[1], max(p[2], 0.0)), res.weights[i])
            return shell[i]

        def in_vert(i: int) -> int:
            if i not in inner:
                inner[i] = part.vert(res.verts[i], res.weights[i])
            return inner[i]

        placket: set[int] = set()
        if g.placket:
            half = 0.012 * res.body.height
            for fi in mine:
                f = t.faces[fi]
                if all(t.chains[i] == "torso" for i in f) and 0.4 <= min(t.u[i] for i in f) and max(t.u[i] for i in f) <= 2.95:
                    cx = sum(res.verts[i][0] for i in f) / len(f)
                    if abs(cx) < half and unit(ct.face_normal(res.verts, f))[1] < -0.3:
                        placket.add(fi)
        faces_before = part.polys
        for fi in sorted(mine):
            if fi in above:
                continue
            f = t.faces[fi]
            color = base_color
            if fi in placket and g.placket:
                color = col[g.placket]
            if fi in cuff_ids and g.cuff:
                color = col[g.cuff[2]]
            if g.sole and all(res.verts[i][2] < 0.03 for i in f):
                color = col[g.sole]
            part.face([out_vert(i) for i in f], color)
        for a, b, fi in rim:                                             # walls down to the skin
            if fi in above:
                continue
            color = col[g.cuff[2]] if (g.cuff and fi in cuff_ids) else base_color
            part.face([in_vert(a), in_vert(b), out_vert(b), out_vert(a)], color)
        if g.buttons:
            _buttons(part, res, g)
        if g.collar:
            _collar(part, res, g, col)
        if g.skirt:
            _skirt(part, res, g, col, [res.verts[i] for i in rim_verts if t.chains[i] == "torso"])
        if g.bib:
            _straps(part, res, g, col)
        stats[g.id] = {"covers": len(mine), "faces": part.polys - faces_before, "layer": g.layer}
    return part, hidden, stats


def _widen(res: ct.BodyResult, tag: str, p: Vec, r_min: float) -> Vec:
    """Push `p` out from the shin bone to at least `r_min` (boot shafts); the foot is widened from the
    line ankle → toe at a smaller radius and keeps its sole on the ground."""
    knee, ankle = res.joints[f"shin.{tag}"]
    if p[2] >= ankle[2]:
        a = unit(sub(ankle, knee))
        d = sub(p, knee)
        lon = dot(d, a)
        radial = sub(d, mul(a, lon))
        r = length(radial)
        if 1e-6 < r < r_min:
            return add(add(knee, mul(a, lon)), mul(radial, r_min / r))
        return p
    toe = res.landmarks[f"toe.{tag}"]
    center = (ankle[0], ankle[1], ankle[2] * 0.5)
    a = unit(sub((toe[0], toe[1], center[2]), center))
    d = sub(p, center)
    lon = dot(d, a)
    radial = sub(d, mul(a, lon))
    r = length(radial)
    rf = 0.75 * r_min
    if 1e-6 < r < rf:
        q = add(add(center, mul(a, lon)), mul(radial, rf / r))
        return (q[0], q[1], max(q[2], 0.0))
    return p


def _buttons(part: Part, res: ct.BodyResult, g: Garment) -> None:
    """Brass buttons down the front, on the garment surface between the chest and the waist."""
    b = res.body
    tris = res.tris(("chest", "waist", "pelvis"))
    for k in range(g.buttons):
        z = b.chest_z - (b.chest_z - b.waist_z) * (0.15 + 0.8 * k / max(g.buttons - 1, 1))
        hit = ct.raycast(tris, (0.0, -1.0, z), (0.0, 1.0, 0.0))
        if hit:
            _box(part, add(hit[1], (0.0, -(g.offset + 0.006), 0.0)), 0.009 * b.height, "brass",
                 surface_weights(res, hit[2], hit[1]))


def _collar(part: Part, res: ct.BodyResult, g: Garment, col: dict[str, str]) -> None:
    """A standing band around the neck base, resting on the garment shell."""
    j = res.landmarks
    nb, hb = j["neck_base"], j["head_base"]
    tris = res.tris(("neck", "chest", "shoulder"))
    w_low, w_high = {"chest": 0.7, "neck": 0.3}, {"chest": 0.35, "neck": 0.65}
    z0 = nb[2] - 0.004
    z1 = nb[2] + (hb[2] - nb[2]) * g.collar
    c0, c1 = (0.0, nb[1], z0), (0.0, nb[1] + 0.3 * (hb[1] - nb[1]), z1)
    r0 = ct.surface_ring(tris, c0, (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), 10, offset=g.offset + 0.006, fallback=0.05)
    r1 = ct.surface_ring(tris, c1, (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), 10, offset=g.offset + 0.012, fallback=0.045)
    a = [part.vert(p, w_low) for p in r0]
    b = [part.vert(p, w_high) for p in r1]
    color = col[g.collar_color or g.color]
    part.loft([a, b], color, lambda k: lerp(c0, c1, 0.5))
    # the inner side, so the band has thickness and reads from above
    r2 = [lerp(p, c1, 0.18) for p in r1]
    d = [part.vert(p, w_high) for p in r2]
    part.loft([b, d], color, lambda k: add(c1, (0.0, 0.0, -0.05)))


def _skirt(part: Part, res: ct.BodyResult, g: Garment, col: dict[str, str], hem_top: list[Vec]) -> None:
    """A coat skirt hanging from the hips: a ring sampled on the hip shell, flaring to `skirt` × leg."""
    b = res.body
    t = res.template
    leg = b.hip_z - b.ankle_z
    crotch = min(res.verts[i][2] for i, c in enumerate(t.chains) if c == "torso")   # apex between the legs
    z_top = crotch + 0.3 * (b.waist_z - crotch)
    z_hem = max(b.hip_z - g.skirt * leg, b.knee_z + 0.1 * leg)
    tris = res.tris(("pelvis", "thigh", "waist"))
    yc = res.landmarks["pelvis_center"][1]
    c_top = (0.0, yc, z_top)
    top = ct.surface_ring(tris, c_top, (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), 12, offset=g.offset + 0.008, fallback=0.12)
    rings_pts = [top]
    for f, flare in ((0.5, 1.07), (1.0, 1.16)):
        z = z_top + (z_hem - z_top) * f
        rings_pts.append([(p[0] * flare * 1.04, yc + (p[1] - yc) * flare, z) for p in top])

    def weights(p: Vec, depth: float) -> Weights:
        if abs(p[0]) < 0.3 * b.hip_x:
            return {"pelvis": 1.0}
        side = "L" if p[0] > 0 else "R"
        k = round(0.5 * depth, 4)
        return {"pelvis": 1 - k, f"thigh.{side}": k} if k > 0 else {"pelvis": 1.0}

    rings = [[part.vert(p, weights(p, d)) for p in pts] for pts, d in zip(rings_pts, (0.0, 0.55, 1.0))]
    part.loft(rings, col[g.color], lambda k: (0.0, yc, (rings_pts[k][0][2] + rings_pts[k + 1][0][2]) / 2))
    # the hem seen from below: an inner ring so the open skirt has thickness
    inner = [part.vert((p[0] * 0.93, yc + (p[1] - yc) * 0.93, p[2] + 0.012), weights(p, 1.0)) for p in rings_pts[-1]]
    part.loft([rings[-1], inner], col[g.color], lambda k: (0.0, yc, z_hem + 0.3))


def _straps(part: Part, res: ct.BodyResult, g: Garment, col: dict[str, str]) -> None:
    """Overall straps from the bib corners over the shoulders to the back of the waist, plus buttons."""
    b = res.body
    tris = res.tris(("chest", "waist", "shoulder", "neck", "pelvis"))
    color = col[g.color]
    width = 0.022 * b.height
    lift = 0.02
    for side in (1, -1):
        x = side * 0.5 * b.shoulder_x
        path: list[tuple[Vec, Vec, int]] = []        # (point, outward, face)
        for z in (b.chest_z - 0.01, (b.chest_z + b.shoulder_z) / 2):
            hit = ct.raycast(tris, (x, -1.0, z), (0.0, 1.0, 0.0))
            if hit:
                path.append((hit[1], (0.0, -1.0, 0.0), hit[2]))
        hit = ct.raycast(tris, (x * 1.05, 0.0, b.height), (0.0, 0.0, -1.0))
        if hit:
            path.append((hit[1], (0.0, 0.0, 1.0), hit[2]))
        for z in ((b.chest_z + b.shoulder_z) / 2, b.waist_z):
            hit = ct.raycast(tris, (x, 1.0, z), (0.0, -1.0, 0.0))
            if hit:
                path.append((hit[1], (0.0, 1.0, 0.0), hit[2]))
        if len(path) < 3:
            continue
        rows = []
        for p, out, fi in path:
            q = add(p, mul(out, lift))
            w = surface_weights(res, fi, p)
            rows.append([part.vert(add(q, (-width / 2, 0.0, 0.0)), w), part.vert(add(q, (width / 2, 0.0, 0.0)), w)])
        for k in range(len(rows) - 1):
            a, c = rows[k], rows[k + 1]
            mid = lerp(path[k][0], path[k + 1][0], 0.5)
            inside = sub(mid, mul(unit(add(path[k][1], path[k + 1][1])), 0.2))
            part.face([a[0], a[1], c[1], c[0]], color, inside)
        p0, out0, fi0 = path[0]
        _box(part, add(p0, mul(out0, lift + 0.004)), 0.012 * b.height, "brass", surface_weights(res, fi0, p0))


def _box(part: Part, c: Vec, r: float, color: str, w: Weights) -> None:
    corners = [(c[0] + sx * r, c[1] + sy * r * 0.6, c[2] + sz * r) for sz in (-1, 1)
               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    idx = [part.vert(p, w) for p in corners]
    for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        part.face([idx[i] for i in f], color, c)


# ---------------------------------------------------------------------------------- body
def body_part(res: ct.BodyResult, hidden: set[int], col: dict[str, str]) -> Part:
    part = Part("body")
    remap: dict[int, int] = {}
    for fi, f in enumerate(res.faces):
        if fi in hidden:
            continue
        idx = []
        for i in f:
            if i not in remap:
                remap[i] = part.vert(res.verts[i], res.weights[i])
            idx.append(remap[i])
        part.face(idx, col["skin"])
    return part


# ---------------------------------------------------------------------------------- head frame
@dataclass
class HeadFrame:
    chin: Vec
    top: Vec
    hh: float                   # chin → crown
    hw: float                   # half width at the eyes (without ears)
    center: Vec                 # middle of the skull (hair and gear are sampled from here)
    tris: list[tuple[Vec, Vec, Vec, int]]
    tris_neck: list[tuple[Vec, Vec, Vec, int]]

    def z(self, b: float) -> float:
        return self.chin[2] + b * self.hh


def head_frame(res: ct.BodyResult) -> HeadFrame:
    t = res.template
    ids = [i for i in t.region_ids(*FACE) if ct.region_base(t.regions[i]) != "ear"]
    chin, top = res.landmarks["chin"], res.landmarks["head_top"]
    hh = top[2] - chin[2]
    eye_z = chin[2] + 0.45 * hh
    near = [i for i in ids if abs(res.verts[i][2] - eye_z) < 0.25 * hh] or ids
    hw = max(abs(res.verts[i][0]) for i in near)
    skull = [res.verts[i] for i in ids]
    yc = (min(p[1] for p in skull) + max(p[1] for p in skull)) / 2
    return HeadFrame(chin, top, hh, hw, (0.0, yc, chin[2] + 0.55 * hh),
                     res.tris([r for r in FACE if r != "ear"]), res.tris([r for r in FACE if r != "ear"] + ["neck"]))


def _face_normal_at(res: ct.BodyResult, fi: int) -> Vec:
    return unit(ct.face_normal(res.verts, res.faces[fi]))


# ---------------------------------------------------------------------------------- face features
EXPRESSIONS = {   # inner-brow drop (fraction), brow lift, mouth shape — as in charlib (procedural)
    "neutral": (0.0, 0.0, "line"), "happy": (-0.1, 0.08, "smile"), "angry": (0.35, -0.05, "frown"),
    "sad": (-0.35, 0.02, "frown"), "scared": (-0.3, 0.2, "open"),
}


def decal(part: Part, res: ct.BodyResult, hf: HeadFrame, outline: list[tuple[float, float]], color: str,
          lift: float, w: Weights | None = None) -> bool:
    """A flat polygon given in face coordinates (x in m, b = height fraction), raycast onto the face
    and lifted along the surface normal — a fan around its centre, so it follows the face planes."""
    cx = sum(p[0] for p in outline) / len(outline)
    cb = sum(p[1] for p in outline) / len(outline)
    pts = []
    for x, b in [(cx, cb), *outline]:
        hit = ct.raycast(hf.tris, (x, hf.center[1] - 1.0, hf.z(b)), (0.0, 1.0, 0.0))
        if hit is None:
            return False
        n = _face_normal_at(res, hit[2])
        if n[1] > 0:
            n = mul(n, -1.0)
        pts.append(add(hit[1], mul(n, lift)))
    weight = w or {"head": 1.0}
    idx = [part.vert(p, weight) for p in pts]
    inside = hf.center
    for k in range(1, len(idx)):
        a, b = idx[k], idx[k + 1] if k + 1 < len(idx) else idx[1]
        part.face([idx[0], a, b], color, inside)
    return True


def ellipse(cx: float, cb: float, rx: float, rb: float, sides: int, rot: float = 0.0) -> list[tuple[float, float]]:
    return [(cx + rx * math.cos(rot + 2 * math.pi * k / sides), cb + rb * math.sin(rot + 2 * math.pi * k / sides))
            for k in range(sides)]


FACE_LAYOUT = {"eye_b": 0.43, "eye_x": 0.44, "eye_rx": 0.25, "eye_rb": 0.1, "brow_b": 0.6, "mouth_b": 0.14}


def face_features(res: ct.BodyResult, params: dict[str, Any], col: dict[str, str], hf: HeadFrame) -> Part:
    """Eyes, lashes, brows and mouth placed from the head geometry (eye line, spacing, mouth line
    are fractions of the head frame — no fixed coordinates)."""
    part = Part("face", outline=False)
    L = {**FACE_LAYOUT, **{k: float(params[f"face_{k}"]) for k in ("eye_b", "eye_x", "mouth_b") if f"face_{k}" in params}}
    size = float(params.get("eye_size", 1.0))
    drop, lift, mouth = EXPRESSIONS.get(params.get("expression", "neutral"), EXPRESSIONS["neutral"])
    hw, hh = hf.hw, hf.hh
    rx, rb = L["eye_rx"] * hw * size, L["eye_rb"] * size
    for side in (-1, 1):
        cx = side * L["eye_x"] * hw
        cb = L["eye_b"]
        inner = -side                                   # toward the nose
        decal(part, res, hf, ellipse(cx, cb, rx, rb, 8, math.pi / 8), "white", 0.002)
        decal(part, res, hf, ellipse(cx + inner * 0.12 * rx, cb - 0.1 * rb, 0.66 * rx, 0.8 * rb, 8, math.pi / 8),
              col["eyes"], 0.004)
        decal(part, res, hf, ellipse(cx + inner * 0.12 * rx, cb - 0.16 * rb, 0.3 * rx, 0.42 * rb, 6), "ink", 0.006)
        decal(part, res, hf, ellipse(cx - inner * 0.28 * rx, cb + 0.34 * rb, 0.16 * rx, 0.2 * rb, 4), "white", 0.008)
        lash = [(cx - rx * 1.05, cb + 0.55 * rb), (cx + rx * 1.05, cb + 0.62 * rb),
                (cx + rx * 1.05 + side * 0.25 * rx, cb + 1.1 * rb), (cx - rx * 0.95, cb + 1.05 * rb)]
        if side < 0:
            lash = [(cx + rx * 1.05, cb + 0.62 * rb), (cx - rx * 1.05, cb + 0.55 * rb),
                    (cx - rx * 1.05 - 0.25 * rx, cb + 1.1 * rb), (cx + rx * 0.95, cb + 1.05 * rb)]
        decal(part, res, hf, lash, "ink", 0.007)
        # brows: over the fringe (anime style) — lifted clear of the bangs; on the skin when there are none
        b_in, b_out = L["brow_b"] + lift - drop * 0.12, L["brow_b"] + lift
        x_in, x_out = cx + inner * 0.8 * rx, cx - inner * 1.0 * rx
        brow = [(x_in, b_in), (x_out, b_out), (x_out, b_out + 0.045), (x_in, b_in + 0.05)]
        bangs = params.get("hair", "short") in HAIR_STYLES and HAIR_STYLES[params.get("hair", "short")]["bangs"]
        decal(part, res, hf, brow, col["hair"], (0.028 + 0.02 * hh) if bangs else 0.004)
    mb = L["mouth_b"]
    mw = 0.22 * hw
    shapes = {"line": [(-mw, mb - 0.012), (mw, mb - 0.012), (mw * 0.9, mb + 0.012), (-mw * 0.9, mb + 0.012)],
              "smile": [(-mw * 1.2, mb + 0.03), (mw * 1.2, mb + 0.03), (mw * 0.6, mb - 0.03), (-mw * 0.6, mb - 0.03)],
              "frown": [(-mw, mb - 0.025), (mw, mb - 0.025), (mw * 0.6, mb + 0.02), (-mw * 0.6, mb + 0.02)],
              "open": [(-mw * 0.6, mb - 0.04), (mw * 0.6, mb - 0.04), (mw * 0.8, mb + 0.03), (-mw * 0.8, mb + 0.03)]}
    decal(part, res, hf, shapes[mouth], "ink", 0.003)
    return part


# ---------------------------------------------------------------------------------- hair
# hem elevation (degrees from the skull centre) at azimuth 0 front · 45 · 90 side · 135 · 180 back
HAIR_STYLES: dict[str, dict[str, Any]] = {
    "short": {"hem": (34, 20, 6, -10, -18), "volume": (0.05, 0.1), "teeth": 2, "depth": 0.08, "bangs": 5,
              "bang_b": 0.64, "locks": 0.26, "spikes": False},
    "messy": {"hem": (34, 18, 2, -14, -22), "volume": (0.06, 0.13), "teeth": 3, "depth": 0.14, "bangs": 6,
              "bang_b": 0.6, "locks": 0.32, "spikes": True},
    "bob": {"hem": (34, 4, -38, -44, -40), "volume": (0.07, 0.12), "teeth": 3, "depth": 0.1, "bangs": 6,
            "bang_b": 0.62, "locks": 0.0, "spikes": False},
}


def _hem(style: dict[str, Any], azimuth: float) -> float:
    keys = style["hem"]
    a = abs(((azimuth + math.pi) % (2 * math.pi)) - math.pi) / (math.pi / 4)     # 0 … 4
    k = min(int(a), 3)
    return math.radians(keys[k] + (keys[k + 1] - keys[k]) * (a - k))


def _sphere_dir(azimuth: float, elevation: float) -> Vec:
    return (math.sin(azimuth) * math.cos(elevation), -math.cos(azimuth) * math.cos(elevation), math.sin(elevation))


def hair(res: ct.BodyResult, params: dict[str, Any], col: dict[str, str], hf: HeadFrame) -> Part:
    part = Part("hair")
    style_name = params.get("hair", "short")
    if style_name == "bald":
        return part
    st = HAIR_STYLES[style_name]
    color = col["hair"]
    w = {"head": 1.0}
    c = hf.center
    n_az, rows = 14, 4
    v_low, v_top = st["volume"]

    def shell_point(az: float, el: float) -> Vec:
        d = _sphere_dir(az, el)
        hit = ct.raycast(hf.tris_neck, c, d)
        r = hit[0] if hit else 0.5 * hf.hh
        vol = hf.hh * (v_low + (v_top - v_low) * max(0.0, math.sin(el)))
        return add(c, mul(d, r + vol))

    grid: list[list[int]] = []
    pts: list[list[Vec]] = []
    for k in range(n_az):
        az = 2 * math.pi * k / n_az
        el0 = _hem(st, az)
        col_pts = [shell_point(az, el0 + (math.radians(84) - el0) * j / rows) for j in range(rows + 1)]
        if style_name == "bob":                                       # flare the hem out a little
            col_pts[0] = add(col_pts[0], mul(unit((col_pts[0][0], col_pts[0][1] - c[1], 0.0)), 0.035 * hf.hh))
        pts.append(col_pts)
        grid.append([part.vert(p, w) for p in col_pts])
    crown = part.vert(add(c, (0.0, 0.0, (hf.top[2] - c[2]) + v_top * hf.hh * 1.05)), w)
    for k in range(n_az):
        a, b = grid[k], grid[(k + 1) % n_az]
        for j in range(rows):
            part.face([a[j], b[j], b[j + 1], a[j + 1]], color, c)
        part.face([a[rows], b[rows], crown], color, c)
    # inner hem band: the shell is open at the bottom — give the edge thickness
    inner = []
    for k in range(n_az):
        p = pts[k][0]
        inner.append(part.vert(lerp(p, (c[0], c[1], p[2]), 0.12), w))
    for k in range(n_az):
        a, b = grid[k][0], grid[(k + 1) % n_az][0]
        part.face([b, a, inner[k], inner[(k + 1) % n_az]], color, add(c, (0.0, 0.0, -hf.hh)))
    # teeth hanging from the hem on the sides and back (never over the face)
    depth = st["depth"] * hf.hh
    for k in range(n_az):
        az = 2 * math.pi * k / n_az
        if abs(((az + math.pi) % (2 * math.pi)) - math.pi) < math.radians(70):
            continue
        p0, p1 = pts[k][0], pts[(k + 1) % n_az][0]
        for m in range(st["teeth"]):
            a0, a1 = lerp(p0, p1, m / st["teeth"]), lerp(p0, p1, (m + 1) / st["teeth"])
            tip = add(lerp(a0, a1, 0.5 + (0.15 if m % 2 else -0.15)), (0.0, 0.0, -depth * (0.7 + 0.3 * (m % 2))))
            ids = [part.vert(a0, w), part.vert(a1, w), part.vert(tip, w)]
            part.face(ids, color, c)
            part.face(list(reversed(ids)), color, add(c, mul(unit(sub(tip, c)), 3.0)))  # both sides
    # fringe: angular bangs from the front hem down over the forehead, in front of the face
    count = st["bangs"]
    span = math.radians(62)
    for m in range(count):
        az0 = -span + 2 * span * m / count
        az1 = -span + 2 * span * (m + 1) / count
        r0, r1 = shell_point(az0, _hem(st, az0) + 0.12), shell_point(az1, _hem(st, az1) + 0.12)
        mid = (az0 + az1) / 2 + (0.08 if m % 2 else -0.06)
        b_tip = st["bang_b"] - (0.05 if m % 2 else 0.0)
        x_tip = math.sin(mid) * hf.hw * 0.95
        hit = ct.raycast(hf.tris, (x_tip, c[1] - 1.0, hf.z(b_tip)), (0.0, 1.0, 0.0))
        if hit is None:
            continue
        tip = add(hit[1], (0.0, -0.012 - 0.02 * hf.hh, 0.0))
        ids = [part.vert(r0, w), part.vert(r1, w), part.vert(tip, w)]
        part.face(ids, color, c)
        part.face(list(reversed(ids)), color, add(tip, (0.0, -1.0, 0.0)))
    # side locks in front of the ears
    if st["locks"]:
        for side in (-1, 1):
            az = side * math.radians(78)
            root = shell_point(az, _hem(st, az) + 0.1)
            for dz, dy in ((0.0, -0.04), (0.02, 0.04)):
                a = add(root, (0.0, dy * hf.hh - 0.02 * hf.hh, dz))
                b = add(root, (0.0, dy * hf.hh + 0.06 * hf.hh, dz))
                tip = add(lerp(a, b, 0.4), (-side * 0.04 * hf.hw, 0.0, -st["locks"] * hf.hh))
                ids = [part.vert(a, w), part.vert(b, w), part.vert(tip, w)]
                part.face(ids, color, c)
                part.face(list(reversed(ids)), color, add(c, (side * 5.0, 0.0, 0.0)))
    if st["spikes"]:
        for az_deg, el_deg in ((0, 70), (60, 58), (-60, 60), (150, 55), (-140, 52), (100, 40), (-95, 42)):
            az, el = math.radians(az_deg), math.radians(el_deg)
            base = shell_point(az, el)
            d = _sphere_dir(az, el + 0.3)
            u, v = ct.frame(d)
            r = 0.09 * hf.hh
            ring = [part.vert(add(base, add(mul(u, r * math.cos(a)), mul(v, r * 0.7 * math.sin(a)))), w)
                    for a in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)]
            tip = part.vert(add(base, mul(d, 0.2 * hf.hh)), w)
            for i in range(4):
                part.face([ring[i], ring[(i + 1) % 4], tip], color, c)
    return part


# ---------------------------------------------------------------------------------- accessories
def goggles(res: ct.BodyResult, params: dict[str, Any], hf: HeadFrame) -> Part:
    part = Part("gear")
    w = {"head": 1.0}
    c = hf.center
    st = HAIR_STYLES.get(params.get("hair", "short"), HAIR_STYLES["short"])
    v_low, v_top = st["volume"] if params.get("hair") != "bald" else (0.0, 0.0)
    n = 16
    rings = []
    for de in (-0.07, 0.07):
        ring = []
        for k in range(n):
            az = 2 * math.pi * k / n
            el = math.radians(26) + de
            d = _sphere_dir(az, el)
            hit = ct.raycast(hf.tris, c, d)
            r = (hit[0] if hit else 0.5 * hf.hh) + hf.hh * (v_low + (v_top - v_low) * math.sin(el)) + 0.012
            ring.append(part.vert(add(c, mul(d, r)), w))
        rings.append(ring)
    part.loft(rings, "ink", lambda k: c)
    for side in (-1, 1):
        az, el = side * math.radians(24), math.radians(27)
        d = _sphere_dir(az, el)
        hit = ct.raycast(hf.tris, c, d)
        r = (hit[0] if hit else 0.5 * hf.hh) + hf.hh * (v_low + (v_top - v_low) * math.sin(el)) + 0.016
        center = add(c, mul(d, r))
        u, v = ct.frame(d)
        rad = 0.16 * hf.hh
        back = [part.vert(add(center, add(mul(u, rad * math.cos(a)), mul(v, rad * math.sin(a)))), w)
                for a in (2 * math.pi * k / 8 + math.pi / 8 for k in range(8))]
        front_c = add(center, mul(d, 0.05 * hf.hh))
        front = [part.vert(add(front_c, add(mul(u, rad * math.cos(a)), mul(v, rad * math.sin(a)))), w)
                 for a in (2 * math.pi * k / 8 + math.pi / 8 for k in range(8))]
        part.loft([back, front], "brass", lambda k, cc=center: sub(cc, mul(d, 0.2)))
        glass_c = add(front_c, mul(d, 0.003))
        glass = [part.vert(add(glass_c, add(mul(u, rad * 0.72 * math.cos(a)), mul(v, rad * 0.72 * math.sin(a)))), w)
                 for a in (2 * math.pi * k / 8 + math.pi / 8 for k in range(8))]
        mid = part.vert(glass_c, w)
        for k in range(8):
            part.face([mid, glass[k], glass[(k + 1) % 8]], "glass", center)
    return part


def scarf(res: ct.BodyResult, col: dict[str, str]) -> Part:
    part = Part("gear")
    j = res.landmarks
    nb, hb = j["neck_base"], j["head_base"]
    tris = res.tris(("neck", "chest", "shoulder"))
    color = col["secondary"]
    rings = []
    specs = ((nb[2] - 0.01, 0.024, {"chest": 0.8, "neck": 0.2}), (nb[2] + 0.35 * (hb[2] - nb[2]), 0.03,
                                                                       {"chest": 0.4, "neck": 0.6}),
             (nb[2] + 0.75 * (hb[2] - nb[2]), 0.02, {"neck": 0.8, "head": 0.2}))
    centers = []
    for z, off, w in specs:
        cc = (0.0, lerp(nb, hb, (z - nb[2]) / max(hb[2] - nb[2], 1e-6))[1], z)
        centers.append(cc)
        pts = ct.surface_ring(tris, cc, (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), 10, offset=off, fallback=0.05)
        rings.append([part.vert(p, w) for p in pts])
    part.loft(rings, color, lambda k: lerp(centers[k], centers[k + 1], 0.5))
    # a tail hanging on the chest, left of centre
    b = res.body
    hit = ct.raycast(res.tris(("chest", "shoulder")), (0.45 * b.shoulder_x, -1.0, nb[2] - 0.03 * b.height),
                     (0.0, 1.0, 0.0))
    if hit:
        top = add(hit[1], (0.0, -0.035, 0.0))
        wt = {"chest": 1.0}
        half = 0.018 * b.height
        drop = 0.07 * b.height
        pts = [add(top, (-half, 0.0, 0.02)), add(top, (half, 0.0, 0.02)), add(top, (half * 1.3, -0.006, -drop)),
               add(top, (-half * 0.5, -0.006, -drop * 0.9))]
        ids = [part.vert(p, wt) for p in pts]
        part.face(ids, color, add(top, (0.0, 1.0, 0.0)))
        part.face(list(reversed(ids)), color, add(top, (0.0, -1.0, 0.0)))
    return part
