"""Character templates: authored low-poly meshes turned into parametric humanoid_v1 bodies.

Pure Python — tests and the backend read it without Blender; builder/charlib.py turns the result into
skinned meshes. Blender axes: Z up, metres, the character faces −Y, its left side is +X (".L").

A template lives in builder/character_templates/<kind>/<id>/:
    template.blend   the mesh a human can open and fix (vertex groups: humanoid_v1 bones + region_*)
    template.json    the same mesh baked for the builder, landmarks, joints and provenance
    preview.png

Two halves:
- **extraction** (once per template, `python -m registry template extract`): a normalized reference mesh
  + its semantic mapping (joint planes, references/characters/<id>/semantic.yaml) → skin weights on
  humanoid_v1 bones (1–2 per vertex), semantic regions, landmarks as affine combinations of vertices
  (they follow every deformation) and a one-time conversion to the humanoid_v1 A-pose;
- **build** (every character build): morphs in template space (bust, head shape, ears) → target
  proportions from params → target skeleton = humanoid.skeleton(target body) → every vertex mapped from
  the template joints to the target joints, blended by its skin weights, cross-sections scaled by
  width / mass profiles. The skeleton comes from the proportions; the mesh follows it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import humanoid as hu

TEMPLATES_DIR = Path(__file__).resolve().parent / "character_templates"
FORMAT = 1

Vec = tuple[float, float, float]
Weights = dict[str, float]

ARM_BONES = ("upper_arm", "forearm", "hand")
LEG_BONES = ("thigh", "shin", "foot")
TORSO_BONES = ("pelvis", "spine", "chest", "neck")


# ---------------------------------------------------------------------------------- vector helpers
def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec) -> Vec:
    n = length(a) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def lerp(a: Vec, b: Vec, t: float) -> Vec:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def centroid(points: Iterable[Vec]) -> Vec:
    pts = list(points)
    n = len(pts) or 1
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def rotate(v: Vec, axis: Vec, angle: float) -> Vec:
    """Rodrigues rotation of `v` around unit `axis`."""
    c, s = math.cos(angle), math.sin(angle)
    k = axis
    kxv = cross(k, v)
    kdv = dot(k, v)
    return (v[0] * c + kxv[0] * s + k[0] * kdv * (1 - c),
            v[1] * c + kxv[1] * s + k[1] * kdv * (1 - c),
            v[2] * c + kxv[2] * s + k[2] * kdv * (1 - c))


def rotation_between(a: Vec, b: Vec) -> tuple[Vec, float]:
    """Axis and angle of the shortest rotation taking unit `a` onto unit `b`."""
    axis = cross(a, b)
    n = length(axis)
    if n < 1e-9:
        return (1.0, 0.0, 0.0), 0.0 if dot(a, b) > 0 else math.pi
    return mul(axis, 1 / n), math.atan2(n, dot(a, b))


FRONT: Vec = (0.0, -1.0, 0.0)


def frame(direction: Vec) -> tuple[Vec, Vec]:
    """Lateral (u) and front-facing (v) axes around `direction` (same convention as charlib._frame)."""
    d = unit(direction)
    u = cross(d, FRONT)
    if length(u) < 1e-6:
        u = (1.0, 0.0, 0.0)
    u = unit(u)
    return u, cross(u, d)


# ---------------------------------------------------------------------------------- mesh helpers
def face_normal(verts: list[Vec], face: list[int]) -> Vec:
    n = (0.0, 0.0, 0.0)
    for i, a in enumerate(face):                                     # Newell normal
        p, q = verts[a], verts[face[(i + 1) % len(face)]]
        n = add(n, ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1])))
    return n                                                          # length = 2 × area


def vertex_normals(verts: list[Vec], faces: list[list[int]]) -> list[Vec]:
    acc = [(0.0, 0.0, 0.0)] * len(verts)
    for f in faces:
        n = face_normal(verts, f)
        for i in f:
            acc[i] = add(acc[i], n)
    return [unit(n) for n in acc]


def triangles(verts: list[Vec], faces: list[list[int]], only: Iterable[int] | None = None
              ) -> list[tuple[Vec, Vec, Vec, int]]:
    keep = None if only is None else set(only)
    out = []
    for fi, f in enumerate(faces):
        if keep is not None and fi not in keep:
            continue
        for k in range(1, len(f) - 1):
            out.append((verts[f[0]], verts[f[k]], verts[f[k + 1]], fi))
    return out


def raycast(tris: list[tuple[Vec, Vec, Vec, int]], origin: Vec, direction: Vec, *, far: bool = False
            ) -> tuple[float, Vec, int] | None:
    """Nearest (or farthest) hit of the ray with the triangles: (distance, point, face index)."""
    best: tuple[float, Vec, int] | None = None
    for a, b, c, fi in tris:
        e1, e2 = sub(b, a), sub(c, a)
        p = cross(direction, e2)
        det = dot(e1, p)
        if abs(det) < 1e-12:
            continue
        inv = 1.0 / det
        s = sub(origin, a)
        u = dot(s, p) * inv
        if u < -1e-7 or u > 1 + 1e-7:
            continue
        q = cross(s, e1)
        v = dot(direction, q) * inv
        if v < -1e-7 or u + v > 1 + 1e-7:
            continue
        t = dot(e2, q) * inv
        if t <= 1e-7:
            continue
        if best is None or (t > best[0] if far else t < best[0]):
            best = (t, add(origin, mul(direction, t)), fi)
    return best


def surface_ring(tris: list[tuple[Vec, Vec, Vec, int]], center: Vec, u: Vec, v: Vec, count: int, *,
                 offset: float = 0.0, fallback: float = 0.05, phase: float = 0.0, far: bool = False) -> list[Vec]:
    """`count` points where rays from `center` in the (u, v) plane leave the surface, pushed out by
    `offset`. Rays that miss use `fallback` metres. Point 0 looks toward +v (the front) rotated by `phase`."""
    pts = []
    for k in range(count):
        a = math.pi / 2 + phase + 2 * math.pi * k / count
        d = unit(add(mul(u, math.cos(a)), mul(v, math.sin(a))))
        hit = raycast(tris, center, d, far=far)
        r = (hit[0] if hit else fallback) + offset
        pts.append(add(center, mul(d, r)))
    return pts


# ---------------------------------------------------------------------------------- semantic mapping
# Default bands (m, around a joint plane) — a vertex inside a band is blended between the two bones.
DEFAULT_BANDS = {"head_base": 0.02, "neck_base": 0.02, "chest": 0.06, "waist": 0.06, "hip": 0.05,
                 "knee": 0.035, "ankle": 0.02, "shoulder": 0.02, "elbow": 0.03, "wrist": 0.015}
BODY_REGIONS = ("head", "neck", "chest", "waist", "pelvis", "shoulder", "upper_arm", "elbow", "forearm", "hand",
                "thigh", "knee", "shin", "calf", "ankle", "foot")
FACE_REGIONS = ("cranium", "forehead", "brow", "eye_region", "cheek", "nose", "jaw", "chin", "ear")
CLOTHING_REGIONS = ("shirt", "jacket", "coat", "vest", "collar", "sleeve", "cuff", "belt", "pants", "shorts",
                    "boot", "shoe")
HAIR_REGIONS = ("hair_cap", "hair_fringe", "hair_side", "hair_back", "hair_accent")


@dataclass
class Semantic:
    """Joint planes of a normalized reference (semantic.yaml). z-planes cut the torso and legs,
    x-planes (|x|, T-pose) cut the arms."""

    pose: str
    planes: dict[str, float]
    bands: dict[str, float]
    tilt: dict[str, float]             # z-plane rises toward the back: z = plane + tilt·y (jaw line, neck)
    armpit: float                      # T-pose: below this z the side of the torso is never arm
    neck_radius: float                 # neck rings: |x| below this
    support_loops: dict[str, float] = field(default_factory=dict)
    face: dict[str, float] = field(default_factory=dict)
    overrides: dict[str, list[int]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Semantic:
        planes = {k: float(v) for k, v in (data.get("planes") or {}).items()}
        missing = [k for k in ("head_base", "neck_base", "chest", "waist", "hip", "knee", "ankle", "shoulder",
                               "elbow", "wrist") if k not in planes]
        if missing:
            raise ValueError("semantic.yaml: missing planes " + ", ".join(missing))
        bands = {**DEFAULT_BANDS, **{k: float(v) for k, v in (data.get("bands") or {}).items()}}
        return cls(pose=str(data.get("pose", "T")), planes=planes, bands=bands,
                   tilt={k: float(v) for k, v in (data.get("tilt") or {}).items()},
                   armpit=float(data.get("armpit", planes["neck_base"] - 0.08)),
                   neck_radius=float(data.get("neck_radius", 0.5 * planes["shoulder"])),
                   support_loops={k: float(v) for k, v in (data.get("support_loops") or {}).items()},
                   face={k: float(v) for k, v in (data.get("face") or {}).items()},
                   overrides={k: [int(i) for i in v] for k, v in (data.get("regions_override") or {}).items()})

    def height(self, v: Vec, plane: str) -> float:
        """Signed height of `v` above a (possibly tilted) z-plane."""
        return v[2] - self.tilt.get(plane, 0.0) * v[1] - self.planes[plane]


def _chain_weights(bones: list[str], joints: list[tuple[float, float]]) -> Weights:
    """Weights along a chain: `joints` are (signed distance past joint k along the chain, band half-width).
    Bone k before joint k, a linear blend inside the band."""
    for k, (d, h) in enumerate(joints):
        if d < -h:
            return {bones[k]: 1.0}
        if d <= h:
            t = (d + h) / (2 * h)
            return {bones[k]: round(1 - t, 4), bones[k + 1]: round(t, 4)} if 0 < t < 1 else {
                bones[k + (1 if t >= 1 else 0)]: 1.0}
    return {bones[-1]: 1.0}


CHAIN_PLANES = {"arm": ("shoulder", "elbow", "wrist"), "leg": ("hip", "knee", "ankle"),
                "torso": ("hip", "waist", "chest", "neck_base", "head_base")}


def chain_u(v: Vec, chain: str, sem: Semantic) -> float:
    """Position along a chain in plane units: 0 at the first joint plane, 1 at the next … (arm: shoulder
    0 · elbow 1 · wrist 2; leg: hip 0 · knee 1 · ankle 2; torso: hip 0 · waist 1 · chest 2 · neck 3 · head 4).
    Garments say where they end in these units, so a sleeve stops on the same edge loop for any body."""
    kind = chain.split(".")[0]
    names = CHAIN_PLANES[kind]
    if kind == "arm":
        h = [abs(v[0]) - sem.planes[n] for n in names]
    elif kind == "leg":
        h = [-sem.height(v, n) for n in names]
    else:
        h = [sem.height(v, n) for n in names]
    for k in range(len(h) - 1):
        if h[k + 1] < 0:
            return k + h[k] / (h[k] - h[k + 1])
    last = len(h) - 1
    seg = h[last - 1] - h[last]
    return last + h[last] / seg if seg > 0 else float(last)


def _side(x: float) -> str | None:
    return "L" if x > 1e-4 else "R" if x < -1e-4 else None


def classify(verts: list[Vec], sem: Semantic) -> tuple[list[Weights], list[str], list[str]]:
    """Skin weights (humanoid_v1 bones), semantic regions and chains ("arm.L", "leg.R", "torso")
    for a normalized T-pose reference. Head sub-regions come from `face_regions`, positions along
    the chains from `chain_u`."""
    P, B = sem.planes, sem.bands
    weights: list[Weights] = []
    regions: list[str] = []
    chains: list[str] = []
    for x, y, z in verts:
        side = _side(x)
        ax = abs(x)
        in_arm_band = sem.armpit <= z < P["neck_base"] + 0.5 * (P["head_base"] - P["neck_base"])   # not the ears
        if side and ax >= P["shoulder"] - B["shoulder"] and in_arm_band:
            tag = side
            w = _chain_weights(["chest", f"upper_arm.{tag}", f"forearm.{tag}", f"hand.{tag}"],
                               [(ax - P[j], B[j]) for j in ("shoulder", "elbow", "wrist")])
            if ax <= P["shoulder"] + B["shoulder"]:
                region = f"shoulder.{tag}"
            elif ax < P["elbow"] - B["elbow"]:
                region = f"upper_arm.{tag}"
            elif ax <= P["elbow"] + B["elbow"]:
                region = f"elbow.{tag}"
            elif ax < P["wrist"] + B["wrist"]:
                region = f"forearm.{tag}"
            else:
                region = f"hand.{tag}"
            chain = f"arm.{tag}"
        elif side and ax > 0.012 and z <= P["hip"] + B["hip"]:
            tag = side
            w = _chain_weights(["pelvis", f"thigh.{tag}", f"shin.{tag}", f"foot.{tag}"],
                               [(-sem.height((x, y, z), j), B[j]) for j in ("hip", "knee", "ankle")])
            if w.get("pelvis", 0.0) >= 0.5:
                region = "pelvis"
            elif z > P["knee"] + B["knee"]:
                region = f"thigh.{tag}"
            elif z >= P["knee"] - B["knee"]:
                region = f"knee.{tag}"
            elif z > P["ankle"] + B["ankle"]:
                region = f"calf.{tag}" if y > 0.0 and z > (P["ankle"] + P["knee"]) / 2 else f"shin.{tag}"
            elif z >= P["ankle"] - B["ankle"]:
                region = f"ankle.{tag}"
            else:
                region = f"foot.{tag}"
            chain = f"leg.{tag}"
        else:
            v = (x, y, z)
            # only the neck column and the head reach the neck / head bones — not the trapezius beside them
            upper = ax < sem.neck_radius * 1.3 or sem.height(v, "head_base") >= -B["head_base"]
            joints = ("waist", "chest", "neck_base", "head_base") if upper else ("waist", "chest")
            bones = ["pelvis", "spine", "chest", "neck", "head"][:len(joints) + 1]
            w = _chain_weights(bones, [(sem.height(v, j), B[j]) for j in joints])
            if sem.height(v, "head_base") >= 0:
                region = "head"
            elif sem.height(v, "neck_base") >= 0 and ax < sem.neck_radius * 1.4:
                region = "neck"
            elif z >= sem.armpit and side and ax > 0.6 * P["shoulder"]:
                region = f"shoulder.{side}"
            elif z >= P["chest"] - B["chest"]:
                region = "chest"
            elif z >= P["waist"] - B["waist"]:
                region = "waist"
            else:
                region = "pelvis"
            chain = "torso"
        weights.append(w)
        regions.append(region)
        chains.append(chain)
    return weights, regions, chains


def face_regions(verts: list[Vec], regions: list[str], sem: Semantic) -> list[str]:
    """Split "head" into cranium, forehead, brow, eye_region, cheek, nose, jaw, chin, ear by the
    fraction of head height (f) and position on the front of the head."""
    F = {"nose": (0.18, 0.42), "chin": 0.2, "jaw": 0.25, "eye": (0.38, 0.64), "brow": (0.52, 0.7),
         "forehead": (0.64, 0.9), "center": 0.3, "front": 0.35, "ear": 1.18, **sem.face}
    head = [i for i, r in enumerate(regions) if r == "head"]
    if not head:
        return regions
    z0 = sem.planes["head_base"]
    top = max(verts[i][2] for i in head)
    ys = [verts[i][1] for i in head]
    y_front, y_back = min(ys), max(ys)
    depth = y_back - y_front
    out = list(regions)
    # half width of the head at a height, ignoring the ear tips
    core = [i for i in head if abs(verts[i][0]) < 0.9 * sem.neck_radius * 2.4]
    hw = max(abs(verts[i][0]) for i in core) if core else 0.1
    for i in head:
        x, y, z = verts[i]
        f = (z - z0) / max(top - z0, 1e-6)
        ax = abs(x) / hw
        front = (y - y_front) / max(depth, 1e-6) < F["front"]
        side = _side(x)
        if ax > F["ear"]:
            out[i] = f"ear.{side}"
        elif front and ax < F["center"] and F["nose"][0] <= f < F["nose"][1]:
            out[i] = "nose"
        elif f < F["chin"] and ax < 0.45 and front:
            out[i] = "chin"
        elif f < F["jaw"] and (y - y_front) / max(depth, 1e-6) < 0.8:
            out[i] = f"jaw.{side}" if side else "chin"
        elif front and F["eye"][0] <= f < F["eye"][1] and ax >= F["center"]:
            out[i] = "eye_region"
        elif front and F["brow"][0] <= f < F["brow"][1]:
            out[i] = "brow"
        elif front and f < F["eye"][0] + 0.04 and side:
            out[i] = f"cheek.{side}"
        elif front and F["forehead"][0] <= f < F["forehead"][1]:
            out[i] = "forehead"
        else:
            out[i] = "cranium"
    return out


def apply_overrides(regions: list[str], sem: Semantic) -> list[str]:
    out = list(regions)
    for region, ids in sem.overrides.items():
        for i in ids:
            if 0 <= i < len(out):
                out[i] = region
    return out


def region_base(region: str) -> str:
    """"calf.L" → "calf"; "head.nose"-style names are not used: face regions are flat names."""
    return region.split(".")[0]


# ---------------------------------------------------------------------------------- landmarks
Landmark = dict[int, float]            # vertex index → coefficient (Σ = 1): an affine combination


def _ring(verts: list[Vec], chains: list[str], chain: str, axis: int, plane: float, band: float,
          extra: Any = None, tilt: float = 0.0) -> list[int]:
    out = []
    for i, v in enumerate(verts):
        if chains[i] != chain:
            continue
        c = abs(v[axis]) if axis == 0 else v[axis] - tilt * v[1]
        if abs(c - plane) <= band and (extra is None or extra(v)):
            out.append(i)
    return out


def _avg(ids: list[int]) -> Landmark:
    if not ids:
        raise ValueError("empty landmark ring — check the planes in semantic.yaml")
    return {i: 1.0 / len(ids) for i in ids}


def find_landmarks(verts: list[Vec], chains: list[str], regions: list[str], sem: Semantic) -> dict[str, Landmark]:
    """Anatomical landmarks of a normalized T-pose reference as affine combinations of vertices."""
    P, B = sem.planes, sem.bands
    lm: dict[str, Landmark] = {}
    head = [i for i, r in enumerate(regions) if region_base(r) in FACE_REGIONS]
    lm["head_top"] = {max(head, key=lambda i: verts[i][2]): 1.0}
    chin = [i for i in head if regions[i] in ("chin",)] or head
    lm["chin"] = {min(chin, key=lambda i: (verts[i][2], abs(verts[i][0]))): 1.0}
    nose = [i for i in head if regions[i] == "nose"]
    if nose:
        lm["nose_tip"] = {min(nose, key=lambda i: verts[i][1]): 1.0}
    ring_band = 0.012
    torso = "torso"
    near_neck = lambda v: abs(v[0]) < sem.neck_radius                                      # noqa: E731
    for name in ("head_base", "neck_base"):
        lm[name] = _avg(_ring(verts, chains, torso, 2, P[name], B[name], near_neck, sem.tilt.get(name, 0.0)))
    for name in ("chest", "waist"):
        ids = _ring(verts, chains, torso, 2, P[name], 0.03)
        lm[f"{name}_center"] = _avg(ids)
    for tag, sign in (("L", 1), ("R", -1)):
        arm, leg = f"arm.{tag}", f"leg.{tag}"
        on_side = lambda v, s=sign: v[0] * s > 0                                              # noqa: E731
        lm[f"shoulder.{tag}"] = _avg(_ring(verts, chains, arm, 0, P["shoulder"], B["shoulder"] + ring_band, on_side))
        lm[f"elbow.{tag}"] = _avg(_ring(verts, chains, arm, 0, P["elbow"], B["elbow"], on_side))
        lm[f"wrist.{tag}"] = _avg(_ring(verts, chains, arm, 0, P["wrist"], B["wrist"] + ring_band, on_side))
        hand = [i for i, c in enumerate(chains) if c == arm and abs(verts[i][0]) > P["wrist"]]
        tip = max(abs(verts[i][0]) for i in hand)
        lm[f"hand_tip.{tag}"] = _avg([i for i in hand if abs(verts[i][0]) >= tip - 0.025])
        for name, band in (("hip", B["hip"]), ("knee", B["knee"] * 0.5), ("ankle", B["ankle"] + ring_band)):
            lm[f"{name}.{tag}"] = _avg(_ring(verts, chains, leg, 2, P[name], band, on_side, sem.tilt.get(name, 0.0)))
        foot = [i for i, c in enumerate(chains) if c == leg and verts[i][2] < P["ankle"] - B["ankle"]]
        lm[f"heel.{tag}"] = {max(foot, key=lambda i: (verts[i][1], -verts[i][2])): 1.0}
        lm[f"toe.{tag}"] = {min(foot, key=lambda i: (verts[i][1], verts[i][2])): 1.0}
    lm["pelvis_center"] = {**{i: w * 0.5 for i, w in lm["hip.L"].items()},
                           **{i: w * 0.5 for i, w in lm["hip.R"].items()}}
    return lm


def evaluate(landmarks: dict[str, Landmark], verts: list[Vec]) -> dict[str, Vec]:
    out = {}
    for name, combo in landmarks.items():
        p = (0.0, 0.0, 0.0)
        for i, c in combo.items():
            p = add(p, mul(verts[i], c))
        out[name] = p
    return out


# ---------------------------------------------------------------------------------- T-pose → A-pose
def to_apose(verts: list[Vec], weights: list[Weights], chains: list[str], lm: dict[str, Vec],
             angle_deg: float = math.degrees(hu.A_POSE)) -> list[Vec]:
    """Lower the arms to the humanoid_v1 A-pose once, at template creation. Every arm vertex turns
    around the shoulder landmark about the front axis by `angle × blend`, where the blend is the arm
    share of its skin weights, softened over the deltoid so the shoulder stays round."""
    out = list(verts)
    for tag, sign in (("L", 1), ("R", -1)):
        sh, wr = lm[f"shoulder.{tag}"], lm[f"wrist.{tag}"]
        d = sub(wr, sh)
        current = math.degrees(math.atan2(-d[2], abs(d[0])))            # already below horizontal
        delta = math.radians(angle_deg - current)
        axis = (0.0, sign * 1.0, 0.0)                                   # +Y turns +X down for the left arm
        inner = abs(sh[0]) * 0.55
        for i, (x, y, z) in enumerate(verts):
            if x * sign <= 0:
                continue
            arm = sum(w for b, w in weights[i].items() if b.split(".")[0] in ARM_BONES)
            if chains[i] != f"arm.{tag}":
                # deltoid / trapezius: the torso above the armpit follows the arm a little
                if chains[i] != "torso" or z < sh[2] - 0.02:
                    continue
                arm = 0.35 * smoothstep((abs(x) - inner) / (abs(sh[0]) - inner))
            if arm <= 0:
                continue
            out[i] = add(sh, rotate(sub((x, y, z), sh), axis, delta * arm))
    return out


# ---------------------------------------------------------------------------------- template data
@dataclass
class Template:
    id: str
    kind: str
    verts: list[Vec]
    faces: list[list[int]]
    weights: list[Weights]
    regions: list[str]
    landmarks: dict[str, Landmark]
    joints: dict[str, Vec]             # template joints (A-pose), = landmarks evaluated on `verts`
    meta: dict[str, Any]
    digest: str = ""
    chains: list[str] = field(default_factory=list)    # per vertex: "torso", "arm.L", "leg.R" …
    u: list[float] = field(default_factory=list)       # per vertex: position along its chain (chain_u)

    def region_ids(self, *names: str) -> list[int]:
        want = set(names)
        return [i for i, r in enumerate(self.regions) if r in want or region_base(r) in want]


def template_dir(kind: str, template_id: str) -> Path:
    return TEMPLATES_DIR / kind / template_id


def template_path(kind: str, template_id: str) -> Path:
    return template_dir(kind, template_id) / "template.json"


@lru_cache(maxsize=8)
def load(template_id: str, kind: str = "body") -> Template:
    path = template_path(kind, template_id)
    if not path.is_file():
        raise FileNotFoundError(f"character template {kind}/{template_id} not found ({path})")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    import hashlib

    return Template(
        id=data["id"], kind=data["kind"],
        verts=[tuple(v) for v in data["mesh"]["verts"]], faces=[list(f) for f in data["mesh"]["faces"]],
        weights=[dict(w) for w in data["weights"]], regions=list(data["regions"]),
        landmarks={k: {int(i): float(c) for i, c in v.items()} for k, v in data["landmarks"].items()},
        joints={k: tuple(v) for k, v in data["joints"].items()},
        meta={k: v for k, v in data.items() if k not in ("mesh", "weights", "regions", "landmarks", "joints",
                                                          "chains", "u")},
        digest=hashlib.sha256(raw.encode()).hexdigest()[:16],
        chains=list(data.get("chains", [])), u=[float(x) for x in data.get("u", [])],
    )


def available(kind: str = "body") -> list[str]:
    root = TEMPLATES_DIR / kind
    return sorted(p.parent.name for p in root.glob("*/template.json")) if root.is_dir() else []


def template_joints(landmarks: dict[str, Vec]) -> dict[str, Vec]:
    """The joints the deformation maps from, named like the landmarks."""
    keep = ("head_top", "head_base", "neck_base", "chest_center", "waist_center", "pelvis_center", "chin",
            "shoulder.L", "shoulder.R", "elbow.L", "elbow.R", "wrist.L", "wrist.R", "hand_tip.L", "hand_tip.R",
            "hip.L", "hip.R", "knee.L", "knee.R", "ankle.L", "ankle.R", "heel.L", "heel.R", "toe.L", "toe.R")
    return {k: landmarks[k] for k in keep if k in landmarks}


# ---------------------------------------------------------------------------------- proportions
@dataclass(frozen=True)
class Shape:
    """Template-relative shape factors from the character params (1.0 = the template)."""

    height: float
    body: float = 1.0                  # body_type: torso widths and limb masses
    head_scale: float = 1.0
    head_width: float = 1.0
    head_depth: float = 1.0
    head_height: float = 1.0
    neck_length: float = 1.0
    neck_width: float = 1.0
    shoulder_width: float = 1.0
    chest_width: float = 1.0
    chest_depth: float = 1.0
    bust: float = 1.0
    glutes: float = 1.0
    waist_width: float = 1.0
    waist_depth: float = 1.0
    pelvis_width: float = 1.0
    pelvis_depth: float = 1.0
    arm_length: float = 1.0
    upper_arm_mass: float = 1.0
    forearm_mass: float = 1.0
    hand_scale: float = 1.0
    hand_thickness: float = 1.0
    leg_length: float = 1.0
    thigh_mass: float = 1.0
    calf_mass: float = 1.0
    foot_scale: float = 1.0

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> Shape:
        names = {f for f in cls.__dataclass_fields__ if f not in ("height", "body")}
        body = {"slim": 0.9, "average": 1.0, "heavy": 1.16}[params.get("body_type", "average")]
        return cls(height=float(params["height"]), body=body,
                   **{n: float(params[n]) for n in names if n in params})


def template_body(t: Template) -> hu.Body:
    """The template's own proportions as a humanoid Body (joints measured from its landmarks)."""
    j = t.joints
    H = j["head_top"][2]
    sh, el, wr, tip = j["shoulder.L"], j["elbow.L"], j["wrist.L"], j["hand_tip.L"]
    hip = (j["hip.L"][2] + j["hip.R"][2]) / 2
    ankle = (j["ankle.L"][2] + j["ankle.R"][2]) / 2
    return hu.Body(
        height=H, width=1.0, shoulder=1.0, head_h=H - j["head_base"][2], neck_h=j["head_base"][2] - j["neck_base"][2],
        ankle_z=ankle, knee_z=(j["knee.L"][2] + j["knee.R"][2]) / 2, hip_z=hip,
        waist_z=j["waist_center"][2], chest_z=j["chest_center"][2], shoulder_z=j["neck_base"][2],
        chin_z=j["head_base"][2], hip_x=(abs(j["hip.L"][0]) + abs(j["hip.R"][0])) / 2,
        shoulder_x=(abs(sh[0]) + abs(j["shoulder.R"][0])) / 2,
        upper_arm=length(sub(el, sh)), forearm=length(sub(wr, el)), hand=length(sub(tip, wr)),
        foot=max(j["ankle.L"][1] - j["toe.L"][1], 0.05) / 0.55, arm_z=sh[2], arm_y=sh[1],
    )


def target_body(t: Template, shape: Shape) -> hu.Body:
    """Target proportions: the template body scaled to `height` and modulated by the shape factors.
    Head, neck and ankle heights are fixed first; the rest splits between legs and torso as in the
    template, `leg_length` moves that split. Height to the crown is exactly `shape.height`."""
    b0 = template_body(t)
    s = shape.height / b0.height
    head_h = b0.head_h * s * shape.head_scale * shape.head_height
    neck_h = b0.neck_h * s * shape.neck_length
    ankle = b0.ankle_z * s
    avail0 = b0.height - b0.head_h - b0.neck_h - b0.ankle_z
    avail = shape.height - head_h - neck_h - ankle
    leg0 = b0.hip_z - b0.ankle_z
    torso0 = b0.shoulder_z - b0.hip_z
    leg = min(avail * leg0 / avail0 * shape.leg_length, 0.72 * avail)
    torso = avail - leg
    hip = ankle + leg
    shoulder_z = hip + torso
    return hu.Body(
        height=shape.height, width=shape.body, shoulder=shape.shoulder_width, head_h=head_h, neck_h=neck_h,
        ankle_z=ankle, knee_z=ankle + leg * (b0.knee_z - b0.ankle_z) / leg0, hip_z=hip,
        waist_z=hip + torso * (b0.waist_z - b0.hip_z) / torso0, chest_z=hip + torso * (b0.chest_z - b0.hip_z) / torso0,
        shoulder_z=shoulder_z, chin_z=shoulder_z + neck_h,
        hip_x=b0.hip_x * s * shape.pelvis_width ** 0.7 * shape.body ** 0.5,
        shoulder_x=b0.shoulder_x * s * shape.shoulder_width * shape.body ** 0.5,
        upper_arm=b0.upper_arm * s * shape.arm_length, forearm=b0.forearm * s * shape.arm_length,
        hand=b0.hand * s * shape.hand_scale, foot=b0.foot * s * shape.foot_scale,
        arm_z=shoulder_z - (b0.shoulder_z - (b0.arm_z or b0.shoulder_z)) * s,
        arm_y=(b0.arm_y or 0.0) * s * shape.chest_depth * shape.body,     # the joint keeps its place in the chest
    )


# ---------------------------------------------------------------------------------- morphs (template space)
@dataclass(frozen=True)
class HeadShape:
    """Head / face shape in template space (1.0 = the template, 0 offsets)."""

    jaw_width: float = 1.0
    jaw_taper: float = 1.0
    chin_width: float = 1.0
    chin_length: float = 1.0
    cheek_width: float = 1.0
    cheek_depth: float = 1.0
    forehead_width: float = 1.0
    brow_depth: float = 1.0
    face_flatness: float = 0.0
    nose_length: float = 1.0
    nose_width: float = 1.0
    nose_projection: float = 1.0
    ear_style: str = "human"
    ear_size: float = 1.0
    ear_angle: float = 0.0
    eye_style: str = "decal"

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> HeadShape:
        kw: dict[str, Any] = {}
        for name, f in cls.__dataclass_fields__.items():
            if name in params:
                kw[name] = params[name] if f.type in ("str", str) else float(params[name])
        return cls(**kw)


EAR_STYLES = ("human", "small", "large", "pointed")


def morph(t: Template, shape: Shape, head: HeadShape) -> list[Vec]:
    """Shape edits that do not move joints, in template space: bust, face planes, ears, eye sockets."""
    verts = list(t.verts)
    j = t.joints
    # -- bust: the front of the chest toward the plane under it (0 flat · 1 template · >1 fuller)
    top, bottom = j["neck_base"][2] - 0.02, j["waist_center"][2] + 0.03
    front_ids = [i for i in t.region_ids("chest", "waist") if verts[i][1] < 0]
    if front_ids and shape.bust != 1.0:
        plane_y = max(verts[i][1] for i in front_ids if abs(verts[i][2] - top) < 0.05 or
                      abs(verts[i][2] - bottom) < 0.05) if front_ids else 0.0
        mid = (top + bottom) / 2
        for i in front_ids:
            x, y, z = verts[i]
            if y >= plane_y:
                continue
            fall = smoothstep(1 - abs(z - mid) / ((top - bottom) / 2))
            verts[i] = (x, plane_y + (y - plane_y) * (1 + (shape.bust - 1) * fall), z)
    # -- glutes: the back of the pelvis toward the plane of the lower back (0 flat · 1 template)
    if shape.glutes != 1.0:
        back = [i for i in t.region_ids("pelvis", "waist", "thigh") if verts[i][1] > 0 and
                (t.chains[i] == "torso" or t.u[i] < 0.5)]
        low, high = j["hip.L"][2] - 0.06, j["waist_center"][2]
        ref = [verts[i][1] for i in back if abs(verts[i][2] - high) < 0.04]
        plane_y = min(ref) if ref else 0.0
        for i in back:
            x, y, z = verts[i]
            if y <= plane_y or not (low <= z <= high):
                continue
            fall = smoothstep((z - low) / 0.06) * smoothstep((high - z) / 0.06)
            verts[i] = (x, plane_y + (y - plane_y) * (1 + (shape.glutes - 1) * fall), z)
    # -- head: every edit is relative to the head frame (base ring → crown)
    hb, crown = j["head_base"], j["head_top"]
    hh = crown[2] - hb[2]
    ids = t.region_ids(*FACE_REGIONS)
    if not ids:
        return verts
    hw = max(abs(verts[i][0]) for i in ids if region_base(t.regions[i]) != "ear")
    y_front = min(verts[i][1] for i in ids)

    def at(i: int, x: float | None = None, y: float | None = None, z: float | None = None) -> None:
        v = verts[i]
        verts[i] = (v[0] if x is None else x, v[1] if y is None else y, v[2] if z is None else z)

    for i in ids:
        r = region_base(t.regions[i])
        x, y, z = verts[i]
        f = (z - hb[2]) / hh
        if r in ("jaw", "chin"):
            taper = 1 + (head.jaw_taper - 1) * (1 - f)                         # narrower toward the chin
            k = (head.chin_width if r == "chin" else head.jaw_width) * taper
            at(i, x=x * k)
            if r == "chin":
                at(i, z=z - (head.chin_length - 1) * 0.12 * hh, y=y - (head.chin_length - 1) * 0.04 * hh)
        elif r == "cheek":
            at(i, x=x * head.cheek_width, y=y + (1 - head.cheek_depth) * 0.08 * hh)
        elif r == "forehead":
            at(i, x=x * head.forehead_width)
        elif r == "brow":
            at(i, y=y - (head.brow_depth - 1) * 0.06 * hh)
        elif r == "nose":
            at(i, x=x * head.nose_width, y=y - (head.nose_projection - 1) * 0.12 * hh,
               z=z - (head.nose_length - 1) * 0.08 * hh)
        elif r == "eye_region" and head.eye_style == "socket":
            at(i, y=y + 0.05 * hh)
    if head.face_flatness > 0:                                                  # pull the face toward one plane
        face = [i for i in ids if region_base(t.regions[i]) in ("nose", "brow", "chin", "cheek", "eye_region",
                                                                 "forehead")]
        plane = max(verts[i][1] for i in face) if face else y_front
        for i in face:
            x, y, z = verts[i]
            at(i, y=y + (plane - y) * head.face_flatness * 0.6)
    # -- ears: the template ear (pointed on the first reference) is one style among four
    for tag, sign in (("L", 1), ("R", -1)):
        ear = [i for i in t.region_ids(f"ear.{tag}")]
        if not ear:
            continue
        tips = sorted(ear, key=lambda i: -abs(verts[i][0]))
        tip = tips[0]
        # the ear base: head vertices that share faces with the tip
        base_ids = sorted({k for f in t.faces if tip in f for k in f if k not in ear})
        base = centroid(verts[k] for k in base_ids) if base_ids else (sign * hw, 0.0, hb[2] + 0.5 * hh)
        out = sub(verts[tip], base)
        if head.ear_style == "pointed":
            v = mul(out, head.ear_size)
        else:                                      # a rounded bump pointing down-back, close to the skull
            k = {"human": 1.0, "small": 0.62, "large": 1.5}.get(head.ear_style, 1.0) * head.ear_size
            v = (sign * 0.1 * hh * k, 0.05 * hh * k, -0.09 * hh * k)
        if head.ear_angle:
            v = rotate(v, (0.0, 0.0, sign * 1.0), math.radians(head.ear_angle))
        verts[tip] = add(base, v)
    return verts


# ---------------------------------------------------------------------------------- deformation
def _profile(z: float, knots: list[tuple[float, float]]) -> float:
    """Smooth piecewise interpolation of (z, value) knots (sorted by z), constant beyond the ends."""
    if z <= knots[0][0]:
        return knots[0][1]
    for (z0, a), (z1, b) in zip(knots, knots[1:]):
        if z <= z1:
            return a + (b - a) * smoothstep((z - z0) / max(z1 - z0, 1e-9))
    return knots[-1][1]


@dataclass
class Deformer:
    """Maps template-space points to the target body. One transform per humanoid bone; a vertex is
    the weighted blend of the transforms of its bones (the same weights the rig uses), so the mesh
    stays continuous across every joint and never has to be re-fitted to an old skeleton."""

    t: Template
    shape: Shape
    b0: hu.Body
    b1: hu.Body
    j1: dict[str, tuple[Vec, Vec]]     # target skeleton (humanoid.skeleton)
    s: float

    @classmethod
    def build(cls, t: Template, shape: Shape) -> Deformer:
        b0 = template_body(t)
        b1 = target_body(t, shape)
        return cls(t, shape, b0, b1, hu.skeleton(b1), shape.height / b0.height)

    # -- torso: one function of the template height for pelvis, spine, chest and neck
    def _torso(self, p: Vec) -> Vec:
        b0, b1, sh, s = self.b0, self.b1, self.shape, self.s
        knots_z = [(b0.hip_z, b1.hip_z), (b0.waist_z, b1.waist_z), (b0.chest_z, b1.chest_z),
                   (b0.shoulder_z, b1.shoulder_z), (b0.chin_z, b1.chin_z)]
        x, y, z = p
        if z <= knots_z[0][0]:
            z1 = knots_z[0][1] + (z - knots_z[0][0]) * s
        elif z >= knots_z[-1][0]:
            z1 = knots_z[-1][1] + (z - knots_z[-1][0]) * s * sh.head_scale
        else:
            for (a0, a1), (c0, c1) in zip(knots_z, knots_z[1:]):
                if z <= c0:
                    z1 = a1 + (z - a0) * (c1 - a1) / (c0 - a0)
                    break
        bw = sh.body
        sx = _profile(z, [(b0.hip_z, sh.pelvis_width * bw), (b0.waist_z, sh.waist_width * bw),
                          (b0.chest_z, sh.chest_width * bw), (b0.shoulder_z, (sh.chest_width * bw + sh.neck_width) / 2),
                          (b0.chin_z, sh.neck_width)]) * s
        sy = _profile(z, [(b0.hip_z, sh.pelvis_depth * bw), (b0.waist_z, sh.waist_depth * bw),
                          (b0.chest_z, sh.chest_depth * bw), (b0.shoulder_z, (sh.chest_depth * bw + sh.neck_width) / 2),
                          (b0.chin_z, sh.neck_width)]) * s
        x1 = x * sx
        # shoulders: the outer upper chest follows the arm root (shoulder_width) instead of chest_width
        arm_z = b0.arm_z or b0.shoulder_z
        inner = 0.45 * b0.shoulder_x
        g = smoothstep((abs(x) - inner) / (b0.shoulder_x - inner)) * smoothstep((z - b0.chest_z) / (arm_z - b0.chest_z))
        if g > 0:
            x1 += math.copysign(g * (self.b1.shoulder_x - b0.shoulder_x * sx), x) * min(1.0, abs(x) / b0.shoulder_x)
            if abs(x) > b0.shoulder_x:        # past the joint the torso moves like the arm root does
                m = sh.upper_arm_mass * bw * s
                x_arm = math.copysign(self.b1.shoulder_x + (abs(x) - b0.shoulder_x) * m, x)
                x1 += (x_arm - x1) * g
        return (x1, y * sy, z1)

    def _head(self, p: Vec) -> Vec:
        sh = self.shape
        k = self.s * sh.head_scale
        hb0 = (0.0, 0.0, self.b0.chin_z)
        d = sub(p, hb0)
        return (d[0] * k * sh.head_width, d[1] * k * sh.head_depth, self.b1.chin_z + d[2] * k * sh.head_height)

    def _segment(self, p: Vec, h0: Vec, t0: Vec, h1: Vec, t1: Vec, mass: tuple[float, float]) -> Vec:
        a0, L0 = unit(sub(t0, h0)), length(sub(t0, h0))
        a1, L1 = unit(sub(t1, h1)), length(sub(t1, h1))
        axis, angle = rotation_between(a0, a1)
        d = sub(p, h0)
        lon = dot(d, a0)
        radial = sub(d, mul(a0, lon))
        u = lon / L0
        if u < 0:
            lon1 = lon * self.s
        elif u > 1:
            lon1 = L1 + (lon - L0) * self.s
        else:
            lon1 = lon * L1 / L0
        m = mass[0] + (mass[1] - mass[0]) * max(0.0, min(1.0, u))
        return add(add(h1, mul(a1, lon1)), mul(rotate(radial, axis, angle), m * self.s))

    def _limb(self, bone: str, p: Vec) -> Vec:
        name, tag = bone.split(".")
        j, j1, sh, bw = self.t.joints, self.j1, self.shape, self.shape.body
        if name == "upper_arm":
            m = sh.upper_arm_mass * bw
            return self._segment(p, j[f"shoulder.{tag}"], j[f"elbow.{tag}"], *j1[bone], (m, m))
        if name == "forearm":
            m = sh.forearm_mass * bw
            return self._segment(p, j[f"elbow.{tag}"], j[f"wrist.{tag}"], *j1[bone], (m, m))
        if name == "hand":                                           # a flat paddle: thickness is its own factor
            h0, t0 = j[f"wrist.{tag}"], j[f"hand_tip.{tag}"]
            h1, t1 = j1[bone]
            a0 = unit(sub(t0, h0))
            axis, angle = rotation_between(a0, unit(sub(t1, h1)))
            u0, _v0 = frame(a0)                                      # across the palm in the A-pose
            d = sub(p, h0)
            d = add(d, mul(u0, dot(d, u0) * (sh.hand_thickness - 1)))
            return add(h1, mul(rotate(d, axis, angle), self.s * sh.hand_scale))
        if name == "thigh":
            m0, m1 = sh.thigh_mass * bw, (sh.thigh_mass + sh.calf_mass) / 2 * bw
            return self._segment(p, j[f"hip.{tag}"], j[f"knee.{tag}"], *j1[bone], (m0, m1))
        if name == "shin":
            m = sh.calf_mass * bw
            return self._segment(p, j[f"knee.{tag}"], j[f"ankle.{tag}"], *j1[bone], (m, 1 + (m - 1) * 0.4))
        if name == "foot":                                           # the sole stays on z = 0
            a0, a1 = j[f"ankle.{tag}"], j1[bone][0]
            d = sub(p, a0)
            k = self.s * sh.foot_scale
            return (a1[0] + d[0] * k * (bw ** 0.5), a1[1] + d[1] * k, a1[2] + d[2] * (a1[2] / a0[2]))
        raise KeyError(bone)

    def point(self, p: Vec, weights: Weights) -> Vec:
        out = (0.0, 0.0, 0.0)
        total = 0.0
        torso: Vec | None = None
        for bone, w in weights.items():
            if w <= 0:
                continue
            if bone in TORSO_BONES or bone == "root":
                torso = torso or self._torso(p)
                q = torso
            elif bone == "head":
                q = self._head(p)
            else:
                q = self._limb(bone, p)
            out = add(out, mul(q, w))
            total += w
        return mul(out, 1 / total) if total else p

    def verts(self, verts: list[Vec]) -> list[Vec]:
        return [self.point(v, w) for v, w in zip(verts, self.t.weights)]


@dataclass
class BodyResult:
    """A deformed template: mesh, rig proportions and landmarks after the deformation."""

    template: Template
    verts: list[Vec]
    body: hu.Body
    joints: dict[str, tuple[Vec, Vec]]
    landmarks: dict[str, Vec]
    normals: list[Vec]

    @property
    def faces(self) -> list[list[int]]:
        return self.template.faces

    @property
    def weights(self) -> list[Weights]:
        return self.template.weights

    def tris(self, regions: Iterable[str] | None = None) -> list[tuple[Vec, Vec, Vec, int]]:
        if regions is None:
            return triangles(self.verts, self.faces)
        ids = set(self.template.region_ids(*regions))
        return triangles(self.verts, self.faces, [fi for fi, f in enumerate(self.faces) if all(i in ids for i in f)])


def build_body(params: dict[str, Any]) -> BodyResult:
    t = load(str(params["body_template"]))
    shape = Shape.from_params(params)
    head = HeadShape.from_params(params)
    d = Deformer.build(t, shape)
    verts = d.verts(morph(t, shape, head))
    return BodyResult(t, verts, d.b1, d.j1, evaluate(t.landmarks, verts), vertex_normals(verts, t.faces))
