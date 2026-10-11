"""Material builds: render preview models + a shader ball with a registry material (inside Blender).

Loads `registry/materials/<id>/blender.py` (build(params, ctx) -> Material, decorate(objects, params, ctx)),
imports the preview GLBs chosen by the planner, lines them up and renders three previews.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Any

import bmesh
import bpy
from mathutils import Vector

import preview

SUN_ENERGY = 3.0


def _load(path: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("registry_material", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for fn in ("build", "decorate"):
        if not callable(getattr(module, fn, None)):
            raise TypeError(f"{path} must define {fn}()")
    return module


def _import_glb(path: str) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for obj in list(new):
        if obj.type == "MESH" and obj.name.endswith("-colonly"):
            bpy.data.objects.remove(obj, do_unlink=True)
            new.remove(obj)
    return new


def _weld(obj: bpy.types.Object) -> None:
    """glTF splits vertices per flat face; weld them so Solidify hulls follow averaged normals."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    for f in bm.faces:
        f.smooth = False
    bm.to_mesh(obj.data)
    bm.free()


def _shader_ball(palette: dict[str, str], x: float) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.45, location=(x, 0, 0.45))
    ball = bpy.context.object
    ball.name = "shader_ball"
    bpy.ops.object.shade_smooth()
    color = palette.get("paint_yellow", "#d6a634").lstrip("#")
    rgb = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    attr = ball.data.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
    attr.data.foreach_set("color_srgb", (rgb + [1.0]) * len(ball.data.loops))
    return ball


def _roots(objs: list[bpy.types.Object]) -> list[bpy.types.Object]:
    return [o for o in objs if o.parent is None or o.parent not in objs]


def _bbox(objs: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in objs:
        if o.type != "MESH":
            continue
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def run(recipe: dict[str, Any], out_dir: Path, log) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:  # type: ignore[no-untyped-def]
    size = int(recipe["preview"]["size"])
    module = _load(recipe["blender_path"])
    ctx = {"sun_energy": SUN_ENERGY, "sun_dir": tuple(preview.SUN_DIRECTION), "resolution": size}

    # line up preview models along X, then the shader ball
    x = 0.0
    meshes: list[bpy.types.Object] = []
    loaded: list[str] = []
    for model in recipe["preview_models"]:
        objs = _import_glb(model["glb"])
        bpy.context.view_layer.update()
        lo, hi = _bbox(objs)
        if math.isinf(lo.x):
            continue
        shift = Vector((x - lo.x, -(lo.y + hi.y) / 2, -lo.z))
        for root in _roots(objs):
            root.location += shift
        x += (hi.x - lo.x) + 0.6
        meshes += [o for o in objs if o.type == "MESH"]
        loaded.append(model["ref"])
        log(f"preview model {model['ref']}: {len(objs)} objects")
    ball = _shader_ball(recipe["palette"]["colors"], x + 0.45)
    meshes.append(ball)

    material = module.build(dict(recipe["params"]), ctx)
    for obj in meshes:
        if obj is not ball:
            _weld(obj)
        obj.data.materials.clear()
        obj.data.materials.append(material)
    module.decorate(meshes, dict(recipe["params"]), ctx)
    bpy.context.view_layer.update()

    # lighting identical to component previews, but the world does not light the toon (camera-only)
    lo, hi = _bbox(meshes)
    files = preview.render(out_dir, size, lo, hi, [], sun_energy=SUN_ENERGY, world_lights=False)

    checks = [
        {"name": "material", "ok": True, "message": f"{material.name}: {len(material.node_tree.nodes)} nodes"},
        {"name": "preview_models", "ok": bool(loaded),
         "message": ", ".join(loaded) if loaded else "no built preview models (only the shader ball)"},
    ]
    stats = {"models": loaded, "nodes": len(material.node_tree.nodes), "outline": recipe["params"].get("outline_mode")}
    return checks, stats, files
