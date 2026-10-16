"""Moving-part clearance: rigid parts that cross each other anywhere in the `work` loop of a built GLB.

Every frame of the loop puts each mesh in world space with every triangle pulled `--shrink` inward
along its normal, so parts that only touch (slippers on a guide bar, a cap on a disc) pass, and
reports each pair of parts whose surfaces cross while they move relative to each other. Parts joined
on purpose (a pin in its eye, a shaft in its bearing, a rod through a gland) are named with
`--joint a:b`: they are still listed, but do not fail the check. Static pairs are not inspected.

Runs in headless Blender (glTF import gives back the generator's Z-up axes):

    blender -b --factory-startup --python-exit-code 1 -P builder/motion_clearance.py -- \
        build/<hash>/model.glb --joint crosshead:conrod --skip exhaust,drain [--json out.json]

Exit code 1 when a pair outside `--joint` crosses.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="motion_clearance")
    p.add_argument("glb", type=Path)
    p.add_argument("--joint", action="append", default=[], help="a:b — parts joined on purpose")
    p.add_argument("--skip", default="", help="comma-separated name fragments to ignore (particles)")
    p.add_argument("--shrink", type=float, default=0.001, help="metres each face is pulled inward")
    p.add_argument("--json", type=Path)
    return p.parse_args(argv)


PALETTE = {name: tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) for name, h in re.findall(
    r"^\s+(\w+):\s*'#([0-9a-fA-F]{6})'", (Path(__file__).resolve().parent.parent / "registry/palette.yaml").read_text(), re.M)}


def colour_name(rgb) -> str:
    """Palette name of a vertex colour: tells which detail of a merged part crosses (brass rings, steel rod)."""
    return min(PALETTE, key=lambda n: sum((a - b) ** 2 for a, b in zip(PALETTE[n], rgb)))


def world_tris(obj: bpy.types.Object, depsgraph, shrink: float) -> tuple[list[Vector], list[tuple[int, int, int]], list[str]]:
    """Independent triangles in world space, each moved `shrink` against its own normal, with colour names."""
    ev = obj.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    mw = ev.matrix_world
    attr = mesh.color_attributes.active_color or (mesh.color_attributes[0] if mesh.color_attributes else None)
    verts: list[Vector] = []
    tris: list[tuple[int, int, int]] = []
    labels: list[str] = []
    for lt in mesh.loop_triangles:
        pts = [mw @ mesh.vertices[i].co for i in lt.vertices]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-12:
            continue
        n.normalize()
        base = len(verts)
        verts.extend(p - n * shrink for p in pts)
        tris.append((base, base + 1, base + 2))
        if attr is None:
            labels.append("?")
        else:
            idx = lt.loops[0] if attr.domain == "CORNER" else lt.vertices[0]
            labels.append(colour_name(attr.data[idx].color_srgb[:3]))
    ev.to_mesh_clear()
    return verts, tris, labels


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse(argv)
    skip = [s for s in args.skip.split(",") if s] + ["-colonly"]  # the builder's merged collision hull
    joints = {frozenset(j.split(":", 1)) for j in args.joint}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.glb))
    scene = bpy.context.scene
    actions = [a for a in bpy.data.actions]
    if actions:
        lo = min(int(a.frame_range[0]) for a in actions)
        hi = max(int(a.frame_range[1]) for a in actions)
    else:
        lo, hi = scene.frame_start, scene.frame_end
    frames = list(range(lo, hi))                                # the last frame repeats the first
    parts = [o for o in scene.objects if o.type == "MESH" and not any(s in o.name for s in skip)]
    names = [o.name for o in parts]

    mats: dict[int, dict[str, object]] = {}
    for f in frames:
        scene.frame_set(f)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mats[f] = {o.name: o.evaluated_get(depsgraph).matrix_world.copy() for o in parts}

    def relative(f: int, a: str, b: str):
        return mats[f][a].inverted() @ mats[f][b]

    moving_pairs = []                                           # pairs that move apart at some frame
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            r0 = relative(frames[0], a, b)
            if any(abs(x - y) > 1e-6 for f in frames[1:] for c0, c1 in zip(r0, relative(f, a, b)) for x, y in zip(c0, c1)):
                moving_pairs.append((a, b))

    hits: dict[tuple[str, str], dict] = {}
    for f in frames:
        scene.frame_set(f)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        geo = {o.name: world_tris(o, depsgraph, args.shrink) for o in parts}
        trees = {n: BVHTree.FromPolygons(v, t) for n, (v, t, _) in geo.items() if t}
        for a, b in moving_pairs:
            if a not in trees or b not in trees:
                continue
            pairs = trees[a].overlap(trees[b])
            if not pairs:
                continue
            (va, ta, la), (vb, tb, lb) = geo[a], geo[b]
            rec = hits.setdefault((a, b), {"frames": [], "max_tris": 0, "where": None, "colours": set()})
            rec["frames"].append(f)
            rec["colours"].update(f"{la[ia]}×{lb[ib]}" for ia, ib in pairs)
            # where they cross: the common part of the boxes of each crossing triangle pair
            lo_, hi_ = [1e9] * 3, [-1e9] * 3
            for ia, ib in pairs:
                pa, pb = [va[k] for k in ta[ia]], [vb[k] for k in tb[ib]]
                for i in range(3):
                    lo_[i] = min(lo_[i], max(min(p[i] for p in pa), min(p[i] for p in pb)))
                    hi_[i] = max(hi_[i], min(max(p[i] for p in pa), max(p[i] for p in pb)))
            if rec["where"]:
                lo_ = [min(x, y) for x, y in zip(lo_, rec["where"][0])]
                hi_ = [max(x, y) for x, y in zip(hi_, rec["where"][1])]
            rec["where"] = [[round(x, 3) for x in lo_], [round(x, 3) for x in hi_]]
            rec["max_tris"] = max(rec["max_tris"], len(pairs))

    report = []
    for (a, b), rec in sorted(hits.items()):
        joint = frozenset((a, b)) in joints
        report.append({"a": a, "b": b, "joint": joint, "frames": len(rec["frames"]),
                       "first": rec["frames"][0], "last": rec["frames"][-1],
                       "max_tris": rec["max_tris"], "where": rec["where"], "colours": sorted(rec["colours"])})
    bad = [r for r in report if not r["joint"]]
    for r in report:
        tag = "joint" if r["joint"] else "CROSS"
        print(f"  {tag:5}  {r['a']} × {r['b']}: {r['frames']}/{len(frames)} frames "
              f"({r['first']}–{r['last']}), up to {r['max_tris']} tri pairs, in box {r['where'][0]} … {r['where'][1]}, "
              f"colours {', '.join(r['colours'])}")
    print(f"motion_clearance: {len(moving_pairs)} moving pairs over {len(frames)} frames, "
          f"{len(bad)} crossing, {len(report) - len(bad)} joints")
    if args.json:
        args.json.write_text(json.dumps({"glb": str(args.glb), "frames": len(frames), "moving_pairs": len(moving_pairs),
                                         "crossing": bad, "joints": [r for r in report if r["joint"]]}, indent=2) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
