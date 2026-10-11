"""Legacy model snapshot: open an existing .blend (or import .fbx/.glb/.obj), render previews, export GLB.

    blender -b --factory-startup [file.blend] --python-exit-code 1 -P builder/legacy_build.py -- \
        --source <path> --format blend|fbx|gltf|obj --out <dir>

Read-only for the source: nothing is saved back. Always writes <out>/report.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import preview  # noqa: E402

GEOMETRY = {"MESH", "CURVE", "SURFACE", "FONT", "META"}


def log(message: str) -> None:
    print(f"[legacy] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="legacy_build.py")
    p.add_argument("--source", required=True)
    p.add_argument("--format", required=True, choices=["blend", "fbx", "gltf", "obj"])
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--size", type=int, default=512)
    return p.parse_args(argv)


def load_source(path: str, fmt: str) -> None:
    if fmt == "blend":
        return  # opened by Blender from the command line
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if fmt == "fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif fmt == "gltf":
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.wm.obj_import(filepath=path)


def visible_geometry() -> list[bpy.types.Object]:
    layer = bpy.context.view_layer
    out = []
    for obj in bpy.context.scene.objects:
        if obj.type not in GEOMETRY or obj.hide_render:
            continue
        try:
            if not obj.visible_get(view_layer=layer):
                continue
        except RuntimeError:
            continue
        out.append(obj)
    return out


def evaluated_stats(objs: list[bpy.types.Object]) -> tuple[dict[str, Any], Vector, Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    polys = tris = verts = 0
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        try:
            mesh = ev.to_mesh()
        except RuntimeError:
            continue
        if mesh is None:
            continue
        mw = ev.matrix_world
        polys += len(mesh.polygons)
        verts += len(mesh.vertices)
        tris += sum(len(p.vertices) - 2 for p in mesh.polygons)
        for corner in obj.bound_box:
            w = mw @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        ev.to_mesh_clear()
    if math.isinf(lo.x):
        lo, hi = Vector((-0.5, -0.5, 0)), Vector((0.5, 0.5, 1))
    dims = hi - lo
    stats = {
        "objects": len(objs), "faces": polys, "tris": tris, "verts": verts,
        "bbox_m": [round(dims.x, 3), round(dims.z, 3), round(dims.y, 3)],   # glTF order: X, Y(up), Z
        "materials": sorted({s.material.name for o in objs for s in o.material_slots if s.material}),
        "actions": sorted(a.name for a in bpy.data.actions if a.users > 0),
        "object_names": sorted(o.name for o in objs)[:60],
    }
    return stats, lo, hi


def focus_bounds(objs: list[bpy.types.Object]) -> tuple[Vector, Vector] | None:
    """Bounds for camera framing without huge flat 'ground' planes that would shrink the model."""
    boxes = []
    for obj in objs:
        pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        boxes.append((obj, lo, hi))

    def union(items: list) -> tuple[Vector, Vector]:
        lo = Vector((min(b[1].x for b in items), min(b[1].y for b in items), min(b[1].z for b in items)))
        hi = Vector((max(b[2].x for b in items), max(b[2].y for b in items), max(b[2].z for b in items)))
        return lo, hi

    def is_flat(b: tuple) -> bool:
        d = b[2] - b[1]
        return d.z <= 0.02 * max(d.x, d.y, 1e-6)

    content = [b for b in boxes if not is_flat(b)]
    if not content or len(content) == len(boxes):
        return None
    clo, chi = union(content)
    area = max((chi.x - clo.x) * (chi.y - clo.y), 1e-6)
    big_flat = [b for b in boxes if is_flat(b) and (b[2].x - b[1].x) * (b[2].y - b[1].y) > 3 * area]
    if not big_flat:
        return None
    return union([b for b in boxes if b not in big_flat])


def export_glb(path: Path, objs: list[bpy.types.Object]) -> None:
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objs)
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
        export_apply=True, export_animations=True, export_cameras=False, export_lights=False,
        export_extras=False, export_materials="EXPORT",
    )


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"status": "failed", "error": None, "source": args.source, "format": args.format,
                              "blender_version": bpy.app.version_string, "warnings": []}
    code = 0
    try:
        load_source(args.source, args.format)
        if args.format == "blend":
            report["file_version"] = ".".join(str(v) for v in bpy.data.version)
        report["scene"] = bpy.context.scene.name
        objs = visible_geometry()
        if not objs:
            raise ValueError("в файле нет видимой геометрии")
        stats, lo, hi = evaluated_stats(objs)
        report["stats"] = stats
        log(f"{len(objs)} objects, {stats['faces']} faces")

        try:
            export_glb(args.out / "model.glb", objs)
        except Exception as exc:  # previews are still useful without a GLB
            report["warnings"].append(f"GLB: {type(exc).__name__}: {exc}")
            log(f"GLB export failed: {exc}")

        # previews: own lights/cameras off, canonical light + neutral background (same as the registry)
        hidden = [o for o in bpy.context.scene.objects if o.type in {"LIGHT", "CAMERA"} or (o.type in GEOMETRY and o not in objs)]
        bpy.context.scene.frame_set(bpy.context.scene.frame_start)
        focus = focus_bounds(objs)
        if focus:
            lo, hi = focus
            report["warnings"].append("кадр по содержимому: большие плоскости-«земля» не учитываются в рамке")
        report["previews"] = preview.render(args.out, args.size, lo, hi, hidden)
        report["status"] = "ok"
    except Exception as exc:
        traceback.print_exc()
        report["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    report["builder_duration_s"] = round(time.monotonic() - started, 2)
    (args.out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"status {report['status']} in {report['builder_duration_s']}s")
    return code


if __name__ == "__main__":
    sys.exit(main())
