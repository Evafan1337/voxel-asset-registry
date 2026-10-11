"""Z-fighting finder: faces of different colours lying in one plane, facing the same way, overlapping.

Two such faces share a depth, so the renderer picks either of them pixel by pixel and the surface
flickers as the camera moves (a brass band on a black rim, a visor flush with the cab roof). Faces
facing each other (a part resting on a host) are culled from outside and are not reported; neither
are overlaps of one colour, which shade identically, nor overlaps backed by an opposite face in the
same plane — the inner sides of plates laid on a closed host (a door and its window on a hull), which
face into the host and are never seen.

Plain Python, no Blender: reads a built GLB (glTF Y-up, rest pose) or takes triangles directly.

    python builder/zfight.py build/<hash>/model.glb
"""

from __future__ import annotations

import json
import math
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

P3 = tuple[float, float, float]
PLANE_TOL = 1e-3          # metres between the planes: closer than this the depth test cannot separate them
NORMAL_TOL = 1e-3         # 1 − cos of the angle between the normals
MIN_AREA = 1e-5           # m² of overlap worth reporting (≈ 3 × 3 mm)


@dataclass(frozen=True)
class Tri:
    a: P3
    b: P3
    c: P3
    color: tuple[int, int, int]
    owner: str


@dataclass
class Issue:
    owners: tuple[str, str]
    colors: tuple[tuple[int, int, int], tuple[int, int, int]]
    normal: P3
    area: float
    at: P3

    def __str__(self) -> str:
        n = ", ".join(f"{v:+.2f}" for v in self.normal)
        p = ", ".join(f"{v:.3f}" for v in self.at)
        hexes = " / ".join("#%02x%02x%02x" % c for c in self.colors)
        return f"{self.owners[0]} × {self.owners[1]} ({hexes}): {self.area * 1e4:.2f} cm², normal ({n}) at ({p})"


# ---------------------------------------------------------------------------------- vectors
def _sub(a: Sequence[float], b: Sequence[float]) -> P3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Sequence[float], b: Sequence[float]) -> P3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# ---------------------------------------------------------------------------------- overlap in a plane
def _clip(poly: list[tuple[float, float]], a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    """Keep the part of a convex polygon left of the directed edge a→b (Sutherland–Hodgman)."""
    def side(p: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        sp, sq = side(p), side(q)
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def _area(poly: list[tuple[float, float]]) -> float:
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def intersect(poly: Sequence[tuple[float, float]], tri: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """The part of a convex 2D polygon inside a 2D triangle (empty when they do not overlap)."""
    out, t = list(poly), list(tri)
    if _area(out) < 0:
        out.reverse()
    if _area(t) < 0:
        t.reverse()
    for i in range(3):
        if len(out) < 3:
            return []
        out = _clip(out, t[i], t[(i + 1) % 3])
    return out if len(out) >= 3 else []


def overlap(t1: Sequence[tuple[float, float]], t2: Sequence[tuple[float, float]]) -> float:
    """Area shared by two 2D triangles."""
    return abs(_area(intersect(t1, t2)))


# ---------------------------------------------------------------------------------- search
def find(tris: Iterable[Tri], *, plane_tol: float = PLANE_TOL, min_area: float = MIN_AREA) -> list[Issue]:
    """Overlaps of differently coloured, same-facing coplanar triangles, merged per owner pair,
    colour pair and plane, largest first."""
    items: list[tuple[Tri, P3, float, tuple]] = []
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for t in tris:
        n = _cross(_sub(t.b, t.a), _sub(t.c, t.a))
        ln = math.sqrt(_dot(n, n))
        if ln < 2e-10:
            continue
        n = (n[0] / ln, n[1] / ln, n[2] / ln)
        d = _dot(n, t.a)
        key = (round(n[0], 2), round(n[1], 2), round(n[2], 2), round(d / plane_tol))
        buckets[key].append(len(items))
        items.append((t, n, d, key))

    found: dict[tuple, Issue] = {}
    for i, (t1, n1, d1, key) in enumerate(items):
        u, v = _basis(n1)
        p1 = [(_dot(p, u), _dot(p, v)) for p in (t1.a, t1.b, t1.c)]
        lo1 = (min(q[0] for q in p1), min(q[1] for q in p1))
        hi1 = (max(q[0] for q in p1), max(q[1] for q in p1))
        for nk in _neighbours(*key[:3]):
            for dk in (key[3] - 1, key[3], key[3] + 1):
                for j in buckets.get((*nk, dk), ()):
                    if j <= i:
                        continue
                    t2, n2, d2, _ = items[j]
                    if t1.color == t2.color or 1 - _dot(n1, n2) > NORMAL_TOL or abs(d1 - d2) > plane_tol:
                        continue
                    p2 = [(_dot(p, u), _dot(p, v)) for p in (t2.a, t2.b, t2.c)]
                    if (hi1[0] <= min(q[0] for q in p2) or max(q[0] for q in p2) <= lo1[0]
                            or hi1[1] <= min(q[1] for q in p2) or max(q[1] for q in p2) <= lo1[1]):
                        continue
                    shared = intersect(p1, p2)
                    area = abs(_area(shared)) if shared else 0.0
                    if area <= 1e-9:
                        continue
                    area -= min(area, _backed(shared, items, buckets, n1, d1, u, v, plane_tol))
                    if area <= 1e-9:
                        continue
                    owners = tuple(sorted((t1.owner, t2.owner)))
                    colors = tuple(sorted((t1.color, t2.color)))
                    k = (owners, colors, key[:3], round(d1, 2))
                    if k in found:
                        found[k].area += area
                    else:
                        at = tuple(sum(c) / 3 for c in zip(t1.a, t1.b, t1.c))
                        found[k] = Issue(owners, colors, n1, area, at)  # type: ignore[arg-type]
    return sorted((x for x in found.values() if x.area >= min_area), key=lambda x: -x.area)


def _backed(poly: list[tuple[float, float]], items: list, buckets: dict, n: P3, d: float, u: P3, v: P3,
            plane_tol: float) -> float:
    """Area of `poly` (in the plane n·p = d) covered by faces in that plane facing the other way."""
    covered = 0.0
    dk = round(-d / plane_tol)
    for nk in _neighbours(-n[0], -n[1], -n[2]):
        for k in (dk - 1, dk, dk + 1):
            for j in buckets.get((*nk, k), ()):
                t, n3, d3, _ = items[j]
                if 1 + _dot(n, n3) > NORMAL_TOL or abs(d + d3) > plane_tol:
                    continue
                part = intersect(poly, [(_dot(p, u), _dot(p, v)) for p in (t.a, t.b, t.c)])
                covered += abs(_area(part)) if part else 0.0
    return covered


def _neighbours(nx: float, ny: float, nz: float) -> list[tuple[float, float, float]]:
    s = 0.01
    return [(round(nx + a * s, 2), round(ny + b * s, 2), round(nz + c * s, 2))
            for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]


def _basis(n: P3) -> tuple[P3, P3]:
    helper = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _cross(n, helper)
    lu = math.sqrt(_dot(u, u))
    u = (u[0] / lu, u[1] / lu, u[2] / lu)
    return u, _cross(n, u)


# ---------------------------------------------------------------------------------- GLB
_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_FORMATS = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_NORMALISE = {5121: 255.0, 5123: 65535.0}


def _accessor(gltf: dict, blob: bytes, index: int) -> list[tuple]:
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    n, fmt = _COMPONENTS[acc["type"]], _FORMATS[acc["componentType"]]
    size = struct.calcsize("<" + fmt)
    stride = view.get("byteStride") or n * size
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    out = []
    for i in range(acc["count"]):
        out.append(struct.unpack_from("<" + fmt * n, blob, start + i * stride))
    if acc.get("normalized") and acc["componentType"] in _NORMALISE:
        k = _NORMALISE[acc["componentType"]]
        out = [tuple(v / k for v in row) for row in out]
    return out


def _matrix(node: dict) -> list[list[float]]:
    if "matrix" in node:
        m = node["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = node.get("translation", (0.0, 0.0, 0.0))
    x, y, z, w = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    sx, sy, sz = node.get("scale", (1.0, 1.0, 1.0))
    rot = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
           [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
           [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[rot[0][0] * sx, rot[0][1] * sy, rot[0][2] * sz, tx],
            [rot[1][0] * sx, rot[1][1] * sy, rot[1][2] * sz, ty],
            [rot[2][0] * sx, rot[2][1] * sy, rot[2][2] * sz, tz],
            [0.0, 0.0, 0.0, 1.0]]


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def _apply(m: list[list[float]], p: Sequence[float]) -> P3:
    return tuple(m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3]  # type: ignore[return-value]
                 for r in range(3))


def read_glb(path: str | Path, skip: Sequence[str] = ()) -> list[Tri]:
    """World-space triangles of every drawn mesh node in the rest pose, coloured by COLOR_0.
    Collision nodes (`-colonly`) and nodes whose name starts with one of `skip` (with their
    children) are left out."""
    data = Path(path).read_bytes()
    _magic, _version, _length = struct.unpack_from("<III", data, 0)
    json_len, _ = struct.unpack_from("<II", data, 12)
    gltf = json.loads(data[20:20 + json_len])
    blob = b""
    off = 20 + json_len
    if off < len(data):
        bin_len, _ = struct.unpack_from("<II", data, off)
        blob = data[off + 8:off + 8 + bin_len]
    tris: list[Tri] = []
    identity = [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]

    def visit(index: int, parent: list[list[float]]) -> None:
        node = gltf["nodes"][index]
        name = node.get("name", f"node{index}")
        if name.endswith("-colonly") or any(name.startswith(s) for s in skip):
            return                                             # collision shapes are never drawn
        world = _mul(parent, _matrix(node))
        if "mesh" in node:
            for prim in gltf["meshes"][node["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4:
                    continue
                attrs = prim["attributes"]
                pos = [_apply(world, p) for p in _accessor(gltf, blob, attrs["POSITION"])]
                cols = _accessor(gltf, blob, attrs["COLOR_0"]) if "COLOR_0" in attrs else [(1.0, 1.0, 1.0)] * len(pos)
                idx = ([i[0] for i in _accessor(gltf, blob, prim["indices"])] if "indices" in prim
                       else list(range(len(pos))))
                for k in range(0, len(idx) - 2, 3):
                    i0, i1, i2 = idx[k], idx[k + 1], idx[k + 2]
                    rgb = tuple(int(round(_srgb(c) * 255)) for c in cols[i0][:3])
                    tris.append(Tri(pos[i0], pos[i1], pos[i2], rgb, name))  # type: ignore[arg-type]
        for child in node.get("children", []):
            visit(child, world)

    scene = gltf["scenes"][gltf.get("scene", 0)]
    for root in scene["nodes"]:
        visit(root, identity)
    return tris


def _srgb(linear: float) -> float:
    """glTF vertex colours are linear; palette comparisons are easier in sRGB."""
    return 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        issues = find(read_glb(arg, skip=("particles", "exhaust", "drain")))
        print(f"{arg}: {len(issues)} z-fighting overlaps")
        for issue in issues[:40]:
            print("  ", issue)
