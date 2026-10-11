"""Editable component workbench, built from frozen resolved recipes.

    blender -b --factory-startup -P builder/blockout_sheet.py -- \
        --manifest manifest.json --out sheet.blend

Manifest positions use the browser/glTF axes (X, up, front). Each component keeps
its original local pivot, hierarchy, sockets and vertex colors. Existing sheets
are never replaced: they may already contain the user's assembly work.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def blender_position(position: Any) -> tuple[float, float, float]:
    """Convert the same positions used by the web workbench to Blender Z-up."""
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise ValueError("member position must have three coordinates [X, up, front]")
    if any(isinstance(value, bool) or not isinstance(value, (float, int))
           or not math.isfinite(value) for value in position):
        raise ValueError("member position coordinates must be finite numbers")
    x, up, front = position
    return float(x), -float(front), float(up)


def validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict) or type(manifest.get("version")) is not int or manifest.get("version") != 1:
        raise ValueError("unsupported sheet manifest: expected version 1")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("sheet must contain at least one component")
    grid = manifest.get("snap_grid", 0.25)
    if isinstance(grid, bool) or not isinstance(grid, (int, float)) or not math.isfinite(grid) or grid <= 0:
        raise ValueError("snap_grid must be a positive finite number")
    refs: set[str] = set()
    for member in members:
        if not isinstance(member, dict):
            raise ValueError("each sheet member must be an object")
        ref = member.get("ref")
        if not isinstance(ref, str) or len(ref.split("/")) != 3 or not ref.startswith("components/"):
            raise ValueError("sheet members must reference components/id/variant")
        _, component_id, vid = ref.split("/")
        if not component_id or not vid or member.get("id") != component_id or member.get("vid") != vid:
            raise ValueError(f"member identity does not match {ref}")
        if ref in refs:
            raise ValueError(f"duplicate sheet member {ref}")
        refs.add(ref)
        blender_position(member.get("position"))
        if not any(member.get(key) for key in ("recipe", "recipe_path", "model_path")):
            raise ValueError(f"{ref} has no recipe or model source")
        if "recipe" in member:
            validate_recipe(member, member["recipe"])
    return manifest


def validate_recipe(member: dict[str, Any], recipe: Any) -> dict[str, Any]:
    if not isinstance(recipe, dict) or recipe.get("kind") != "components":
        raise ValueError(f"{member['ref']}: only resolved component recipes are supported")
    if recipe.get("id") != member["id"] or recipe.get("variant") != member["vid"]:
        raise ValueError(f"{member['ref']}: recipe identity mismatch")
    if member.get("hash") and recipe.get("hash") != member["hash"]:
        raise ValueError(f"{member['ref']}: recipe hash mismatch")
    parts = recipe.get("parts")
    if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], dict) or not isinstance(parts[0].get("component"), dict):
        raise ValueError(f"{member['ref']}: expected one resolved component part")
    if not isinstance(recipe.get("palette"), dict) or not isinstance(recipe["palette"].get("colors"), dict):
        raise ValueError(f"{member['ref']}: recipe palette is missing")
    return recipe


def workbench_bounds(lo: Any, hi: Any, grid: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """A modest floor around the parts, with a clear assembly strip at the front."""
    margin = max(0.5, grid * 2)
    front = max(2.0, (hi[1] - lo[1]) * 0.5)
    snap_down = lambda value: math.floor(value / grid) * grid
    snap_up = lambda value: math.ceil(value / grid) * grid
    floor = min(0.0, lo[2]) - 0.03
    return ((snap_down(lo[0] - margin), snap_down(lo[1] - front), floor),
            (snap_up(hi[0] + margin), snap_up(hi[1] + margin), floor))


def _resolve_path(value: str, manifest_path: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else manifest_path.parent / path


def _material_namespace(bpy: Any, materials_before: set[int], prefix: str) -> None:
    # voxlib caches surface materials by name. Renaming after each member makes
    # the next palette build independent, without changing the shared builder.
    for material in bpy.data.materials:
        if material.as_pointer() not in materials_before:
            material.name = f"{prefix}::{material.name}"


def _freeze_rest_pose(bpy: Any, objects: list[Any]) -> None:
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    bases = [(obj, obj.matrix_basis.copy()) for obj in objects]
    for obj, basis in bases:
        obj.animation_data_clear()
        obj.matrix_basis = basis
        if obj.data is not None:
            obj.data.animation_data_clear()
            shape_keys = getattr(obj.data, "shape_keys", None)
            if shape_keys is not None:
                shape_keys.animation_data_clear()
    for action in list(bpy.data.actions):
        if action.users == 0:
            bpy.data.actions.remove(action)
    bpy.context.view_layer.update()


def _build_member(bpy: Any, build: Any, voxlib: Any, member: dict[str, Any], manifest_path: Path) -> tuple[Any, list[Any]]:
    from mathutils import Matrix

    namespace = f"{member['id']}@{member['vid']}"
    collection = bpy.data.collections.new(namespace)
    bpy.context.scene.collection.children.link(collection)
    collection["registry_sheet_member"] = True
    collection["registry_ref"] = member["ref"]
    materials_before = {material.as_pointer() for material in bpy.data.materials}
    mesh_data_before = {mesh.as_pointer() for mesh in bpy.data.meshes}
    if member.get("recipe") or member.get("recipe_path"):
        recipe = member.get("recipe")
        if recipe is None:
            recipe = json.loads(_resolve_path(member["recipe_path"], manifest_path).read_text(encoding="utf-8"))
        validate_recipe(member, recipe)
        voxlib.configure_surfaces(recipe["palette"])
        result, objects, _actions = build.run_part(recipe["parts"][0], recipe["palette"]["colors"])
        tops = [result]
    else:
        before = {obj.as_pointer() for obj in bpy.data.objects}
        bpy.ops.import_scene.gltf(filepath=str(_resolve_path(member["model_path"], manifest_path)))
        objects = [obj for obj in bpy.data.objects if obj.as_pointer() not in before]
        tops = [obj for obj in objects if obj.parent is None]
    if not any(obj.type == "MESH" for obj in objects):
        raise ValueError(f"{member['ref']}: source contains no meshes")
    _freeze_rest_pose(bpy, objects)
    _material_namespace(bpy, materials_before, namespace)
    root = bpy.data.objects.new(f"{member.get('title') or member['id']} [{namespace}]", None)
    collection.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.25
    root.show_name = True
    root["registry_sheet_member"] = True
    root["registry_ref"] = member["ref"]
    root["registry_variant"] = member["vid"]
    root["registry_hash"] = member.get("hash", "")
    root["registry_pivot"] = "component_origin"
    for obj in objects:
        if obj.type == "MESH" and obj.data.as_pointer() in mesh_data_before:
            obj.data = obj.data.copy()
        for old_collection in list(obj.users_collection):
            old_collection.objects.unlink(obj)
        collection.objects.link(obj)
        obj.hide_select = False
        obj["registry_sheet_ref"] = member["ref"]
        if build.base_name(obj.name).startswith("socket_"):
            obj["registry_socket"] = build.base_name(obj.name)[len("socket_"):]
    # Keep all local geometry and pivots intact. Only this wrapper is translated.
    for top in tops:
        world = top.matrix_world.copy()
        top.parent = root
        top.matrix_parent_inverse = Matrix.Identity(4)
        top.matrix_world = world
    root.location = blender_position(member["position"])
    bpy.context.view_layer.update()
    return root, objects


def _geometry_bounds(objects: list[Any]) -> tuple[Any, Any]:
    from mathutils import Vector

    points = [obj.matrix_world @ Vector(corner) for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    if not points:
        raise ValueError("workbench contains no geometry")
    return (Vector(tuple(min(point[i] for point in points) for i in range(3))),
            Vector(tuple(max(point[i] for point in points) for i in range(3))))


def _add_helpers(bpy: Any, lo: Any, hi: Any, grid: float) -> Any:
    collection = bpy.data.collections.new("Workbench • helpers (hide to assemble)")
    bpy.context.scene.collection.children.link(collection)
    collection["registry_sheet_helpers"] = True
    collection.hide_select = True
    floor_lo, floor_hi = workbench_bounds(lo, hi, grid)
    x0, y0, floor = floor_lo
    x1, y1, _ = floor_hi
    mesh = bpy.data.meshes.new("workbench_floor")
    mesh.from_pydata([(x0, y0, floor), (x1, y0, floor), (x1, y1, floor), (x0, y1, floor)], [], [(0, 1, 2, 3)])
    surface = bpy.data.objects.new("Workbench floor", mesh)
    collection.objects.link(surface)
    material = bpy.data.materials.new("workbench_neutral")
    material.diffuse_color = (0.19, 0.21, 0.24, 1.0)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = material.diffuse_color
    bsdf.inputs["Roughness"].default_value = 0.9
    mesh.materials.append(material)
    curves = bpy.data.curves.new("workbench_grid", "CURVE")
    curves.dimensions = "3D"
    curves.bevel_depth = min(grid / 100, 0.0025)
    curves.bevel_resolution = 0
    for axis, start, end in ((0, x0, x1), (1, y0, y1)):
        for index in range(round((end - start) / grid) + 1):
            value = start + index * grid
            points = ((value, y0, floor + 0.003), (value, y1, floor + 0.003)) if axis == 0 else (
                (x0, value, floor + 0.003), (x1, value, floor + 0.003))
            spline = curves.splines.new("POLY")
            spline.points.add(1)
            for point, coordinate in zip(spline.points, points):
                point.co = (*coordinate, 1.0)
    grid_object = bpy.data.objects.new(f"Grid {grid:g} m", curves)
    collection.objects.link(grid_object)
    grid_material = bpy.data.materials.new("workbench_grid")
    grid_material.diffuse_color = (0.34, 0.37, 0.41, 1.0)
    curves.materials.append(grid_material)
    text = bpy.data.curves.new("workbench_hint", "FONT")
    text.body = f"ASSEMBLY WORKSPACE  |  grid {grid:g} m"
    text.size = min(0.18, (x1 - x0) / max(len(text.body), 1) * 1.4)
    text_object = bpy.data.objects.new("Assembly workspace", text)
    text_object.location = (x0 + 0.25, y0 + 0.5, floor + 0.008)
    collection.objects.link(text_object)
    for obj in collection.objects:
        obj.hide_select = True
        obj["registry_sheet_helper"] = True
    return collection


def _configure_workspace(bpy: Any, lo: Any, hi: Any, grid: float) -> None:
    from mathutils import Euler

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.frame_start = scene.frame_end = 0
    scene.tool_settings.use_snap = True
    scene.tool_settings.snap_elements = {"INCREMENT"}
    scene.tool_settings.use_snap_grid_absolute = True
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.shading.type = "MATERIAL"
            space.overlay.show_floor = True
            space.overlay.grid_scale = grid
            space.overlay.grid_subdivisions = 1
            space.clip_start = 0.01
            space.clip_end = 1000.0
            space.region_3d.view_location = (lo + hi) / 2
            space.region_3d.view_distance = max((hi - lo).length * 1.3, 3.0)
            space.region_3d.view_rotation = Euler((math.radians(55), 0.0, math.radians(35))).to_quaternion()
            space.region_3d.view_perspective = "PERSP"
    instructions = bpy.data.texts.new("READ ME • component workbench")
    instructions.write("COMPONENT WORKBENCH\n\n"
                       "Each component is an independent collection; move its named root to move the whole part.\n"
                       "Duplicate a collection in the Outliner, or Select Objects in that collection and Shift+D.\n"
                       "Alt+D duplicates selected objects with linked mesh data; edit one mesh to change its copies.\n"
                       f"G: move, R: rotate; Ctrl while moving toggles snapping. Grid: {grid:g} metres.\n"
                       "Socket empties keep the original component mount positions and axes.\n"
                       "All parts are frozen at frame 0. The front strip is free space for your assembly.\n"
                       "Helpers can be hidden in the Outliner. Save your assembly under a new filename.\n")


def save_sheet(manifest: dict[str, Any], manifest_path: Path, out: Path, *,
               preview_dir: Path | None = None, model_path: Path | None = None,
               previews_only: bool = False) -> dict[str, Any]:
    validate_manifest(manifest)
    if previews_only and preview_dir is None:
        raise ValueError("previews_only requires a preview directory")
    if out.exists() and not previews_only:
        raise FileExistsError(f"existing workbench will not be overwritten: {out}")
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import bpy
    import build
    import voxlib

    build.reset_scene()
    all_objects: list[Any] = []
    roots: list[Any] = []
    for member in manifest["members"]:
        root, objects = _build_member(bpy, build, voxlib, member, manifest_path)
        roots.append(root)
        all_objects.extend(objects)
    lo, hi = _geometry_bounds(all_objects)
    grid = float(manifest.get("snap_grid", 0.25))
    helpers = _add_helpers(bpy, lo, hi, grid)
    _configure_workspace(bpy, lo, hi, grid)
    scene = bpy.context.scene
    scene["registry_sheet_id"] = str(manifest.get("id", ""))
    scene["registry_sheet_hash"] = str(manifest.get("hash", ""))
    scene["registry_sheet_manifest"] = json.dumps(manifest, ensure_ascii=False)
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    roots[0].select_set(True)
    bpy.context.view_layer.objects.active = roots[0]
    report: dict[str, Any] = {"status": "ok", "members": len(roots), "objects": len(all_objects),
                              "bbox_blender": {"min": list(lo), "max": list(hi)}, "snap_grid": grid}
    out.parent.mkdir(parents=True, exist_ok=True)
    if not previews_only:
        temporary = out.with_name(f".{out.stem}.{uuid.uuid4().hex}.blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(temporary), compress=True, check_existing=False)
            # Atomic, exclusive creation: a user saving this path during export wins.
            os.link(temporary, out)
        finally:
            temporary.unlink(missing_ok=True)
    if model_path is not None:
        model_path.parent.mkdir(parents=True, exist_ok=True)
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in roots + all_objects:
            obj.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(model_path), export_format="GLB", use_selection=True,
                                  export_yup=True, export_apply=True, export_extras=True,
                                  export_vertex_color="ACTIVE", export_animations=False,
                                  export_cameras=False, export_lights=False)
    if preview_dir is not None:
        import preview
        preview_dir.mkdir(parents=True, exist_ok=True)
        report["previews"] = preview.render(preview_dir, 900, lo, hi, list(helpers.objects))
    out.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview", type=Path, help="isometric and six geometry-only orthographic PNGs")
    parser.add_argument("--previews-only", action="store_true", help="render recipes without writing a .blend")
    parser.add_argument("--model", type=Path, help="optional geometry-only GLB (no workbench helpers)")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = save_sheet(manifest, args.manifest, args.out, preview_dir=args.preview, model_path=args.model,
                            previews_only=args.previews_only)
        print(f"[blockout-sheet] {json.dumps(report)}", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
