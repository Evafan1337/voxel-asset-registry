"""Headless build entry point.

    blender -b --factory-startup -P builder/build.py -- --recipe <recipe.json> --out <dir>

Reads a resolved recipe (written by the backend), runs component generators (or loads the .blend
of a manual variant), assembles assets by sockets, validates, exports GLB and renders previews.
Always writes <out>/report.json; exits non-zero on exceptions so the backend can mark the build
as failed. With --save-blend <path> it only saves the generated component as an editable .blend.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import struct
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

import checks  # noqa: E402
import material_build  # noqa: E402
import preview  # noqa: E402
import voxlib  # noqa: E402

_SUFFIX_RE = re.compile(r"\.\d{3}$")


def log(message: str) -> None:
    print(f"[builder] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="builder/build.py")
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--save-blend", type=Path, help="save the generated component as .blend and stop")
    return parser.parse_args(argv)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start = 0
    scene.frame_end = 0


def base_name(name: str) -> str:
    return _SUFFIX_RE.sub("", name)


# ---------------------------------------------------------------------- generators

def load_generator(path: str, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load generator {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "build", None)):
        raise TypeError(f"{path} must define build(params: dict) -> bpy.types.Object")
    return module


def load_source(path: str, name: str) -> bpy.types.Object:
    """Manual variant: append the objects saved in its .blend instead of running generator.py.

    Only meshes and empties (sockets, pivots of moving parts) are kept. Every mesh is switched to
    the shared palette material, so colors come from the "Color" attribute as in generated
    meshes. The root is the object marked `registry_root` when the file was seeded; otherwise
    the single top-level object, or a new empty if the author left several.
    """
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    loaded = [o for o in dst.objects if o is not None]
    for obj in [o for o in loaded if o.type not in ("MESH", "EMPTY")]:
        log(f"source {Path(path).name}: skipping {obj.type.lower()} '{obj.name}'")
        loaded.remove(obj)
        bpy.data.objects.remove(obj, do_unlink=True)
    if not loaded:
        raise ValueError(f"{path} has no mesh or empty objects")
    material = voxlib.palette_material()
    for mesh in {o.data for o in loaded if o.type == "MESH"}:
        mesh.materials.clear()
        mesh.materials.append(material)
        for poly in mesh.polygons:
            poly.material_index = 0
    for stale in [m for m in bpy.data.materials if m is not material and m.users == 0]:
        bpy.data.materials.remove(stale)
    marked = [o for o in loaded if o.get("registry_root")]
    for obj in marked:
        del obj["registry_root"]  # the marker must not reach glTF extras
    tops = [o for o in loaded if o.parent is None]
    if marked:
        return marked[0]
    if len(tops) == 1:
        return tops[0]
    root = bpy.data.objects.new(name, None)  # run_part parents the remaining top-level objects
    return voxlib.link(root)


def seed_blend(recipe: dict[str, Any], path: Path) -> None:
    """Save a component or an asset, exactly as the builder assembles it, as the .blend of a
    manual variant.

    An asset keeps one object tree per slot, named after the slot and parented to the slot it
    is mounted on, so moving a host in Blender carries everything standing on it.
    """
    if recipe["kind"] == "components" or recipe.get("manual"):
        result, _objects, _actions = run_part(recipe["parts"][0], recipe["palette"]["colors"])
    else:
        roots: dict[str, bpy.types.Object] = {}
        assembled: dict[str, bpy.types.Object] = {}
        assemble(recipe, part_roots=assembled)
        for part in recipe["parts"]:                             # hosts come first
            top = assembled[part["slot"]]
            top["registry_slot"] = part["slot"]
            top["registry_ref"] = part["ref"]
            host = roots.get(part.get("host"))
            if host is not None and not follows_animation(top.parent):
                bpy.context.view_layer.update()
                world = top.matrix_world.copy()
                top.parent = host
                top.matrix_parent_inverse = Matrix.Identity(4)
                top.matrix_world = world
            top.name = part["slot"]
            roots[part["slot"]] = top
        result = next(iter(roots.values()))                       # the body slot
    result["registry_root"] = True
    scene = bpy.context.scene
    scene.frame_end = max((int(a.frame_range[1]) for a in bpy.data.actions), default=voxlib.LOOP_FRAMES)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    log(f"saved {path}")


def run_part(part: dict[str, Any], palette: dict[str, str]
             ) -> tuple[bpy.types.Object, list[bpy.types.Object], list[bpy.types.Action]]:
    comp = part["component"]
    voxlib.configure(palette, float(comp["interface"]["voxel_size"]), int(comp["level"]))
    objects_before = {o.as_pointer() for o in bpy.data.objects}
    actions_before = {a.as_pointer() for a in bpy.data.actions}
    if "source_path" in comp:
        log(f"manual {comp['id']}@{comp['variant']} source={comp['source_path']}")
        result = load_source(comp["source_path"], comp["id"])
    else:
        module = load_generator(comp["generator_path"], f"generator_{comp['id']}_{part['slot'] or 'root'}")
        log(f"generator {comp['id']}@{comp['variant']} level={comp['level']} params={json.dumps(comp['params'])}")
        result = module.build(dict(comp["params"]))
    if not isinstance(result, bpy.types.Object):
        raise TypeError(f"{comp['id']}.build() must return bpy.types.Object, got {type(result).__name__}")
    created = [o for o in bpy.data.objects if o.as_pointer() not in objects_before]
    if result not in created:
        created.append(result)
    for obj in created:
        voxlib.link(obj)
    bpy.context.view_layer.update()
    for obj in created:  # stray top-level objects belong to the generator's root
        if obj is not result and obj.parent is None:
            world = obj.matrix_world.copy()
            obj.parent = result
            obj.matrix_world = world
    actions = [a for a in bpy.data.actions if a.as_pointer() not in actions_before]
    return result, created, actions


def run_asset_part(part: dict[str, Any], palette: dict[str, str]
                   ) -> tuple[bpy.types.Object, list[bpy.types.Object], list[bpy.types.Action]]:
    """Build a referenced asset recursively in the same scene, preserving its animation and sockets."""
    child = part["asset"]
    before_objects = {o.as_pointer() for o in bpy.data.objects}
    before_actions = {a.as_pointer() for a in bpy.data.actions}
    tops = assemble({"kind": "assets", "palette": {"colors": palette},
                     "parts": child["parts"], "interface": child["interface"],
                     "export_sockets": child.get("export_sockets", False)})
    root = bpy.data.objects.new(f"subasset_{child['id']}", None)
    voxlib.link(root)
    for obj in tops:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_world = world
    root["asset_id"] = child["id"]
    root["variant_id"] = child["variant"]
    root["hash"] = child["hash"]
    created = [o for o in bpy.data.objects if o.as_pointer() not in before_objects]
    actions = [a for a in bpy.data.actions if a.as_pointer() not in before_actions]
    return root, created, actions


def rename_part(slot: str, objects: list[bpy.types.Object], actions: list[bpy.types.Action], *,
                keep_sockets: bool) -> None:
    for obj in objects:
        name = base_name(obj.name)
        if name.startswith("socket_"):
            if not keep_sockets:
                obj.name = f"socket_{slot}_{name[len('socket_'):]}"
        else:
            obj.name = f"{slot}_{name}"
    for action in actions:
        action.name = f"{slot}_{base_name(action.name)}"


# ---------------------------------------------------------------------- assembly

def _socket_map(objects: list[bpy.types.Object]) -> dict[str, bpy.types.Object]:
    return {base_name(o.name)[len("socket_"):]: o for o in objects if base_name(o.name).startswith("socket_")}


def expose_asset_sockets(recipe: dict[str, Any], sockets_by_slot: dict[str, dict[str, bpy.types.Object]],
                         tops: list[bpy.types.Object]) -> None:
    """Expose declared asset sockets, including aliases to free subassembly sockets."""
    if not recipe.get("export_sockets"):
        return
    interface = recipe.get("interface") or {}
    if not tops:
        return
    own_objects = [o for top in tops for o in (top, *top.children_recursive)]
    existing = {base_name(o.name)[len("socket_"):] for o in own_objects
                if base_name(o.name).startswith("socket_")}
    for spec in interface.get("sockets", []):
        name = spec["name"]
        if name in existing:
            continue
        host, dot, inner = name.partition(".")
        target = sockets_by_slot.get(host, {}).get(inner) if dot else None
        alias = bpy.data.objects.new(f"socket_{name}", None)
        alias.empty_display_type = "PLAIN_AXES"
        voxlib.link(alias)
        alias.parent = tops[0]
        alias.matrix_parent_inverse = Matrix.Identity(4)
        if target is not None:
            alias.matrix_world = target.matrix_world.copy()
        else:
            x, y, z = spec.get("position", (0.0, 0.0, 0.0))
            rx, ry, rz = spec.get("rotation", (0.0, 0.0, 0.0))
            gltf_rotation = Euler(tuple(math.radians(v) for v in (rx, ry, rz))).to_matrix()
            axis = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
            rotation = (axis @ gltf_rotation @ axis.transposed()).to_4x4()
            alias.matrix_world = Matrix.Translation((x, -z, y)) @ rotation
        alias["socket"] = name
        alias["socket_type"] = spec.get("type", "generic")
        existing.add(name)


def follows_animation(obj: bpy.types.Object | None) -> bool:
    """Only explicitly marked joints change the legacy static attachment behavior."""
    while obj is not None:
        if obj.get("follow_animation", False):
            return True
        obj = obj.parent
    return False


def assemble(recipe: dict[str, Any], *, part_roots: dict[str, bpy.types.Object] | None = None
             ) -> list[bpy.types.Object]:
    """Build all parts in recipe order (hosts first); returns top-level objects for the root.

    A part with host=None/socket=None is the body. Any other part is placed on socket
    `part.socket` of the part in slot `part.host` (the body or another structure).
    Optional part_roots records every slot, including children that follow animated joints.
    """
    palette = recipe["palette"]["colors"]
    parts = recipe["parts"]
    if recipe["kind"] == "components" or recipe.get("manual"):   # one generator or one .blend
        result, _objs, _actions = run_part(parts[0], palette)
        return [result]

    sockets_by_slot: dict[str, dict[str, bpy.types.Object]] = {}
    tops: list[bpy.types.Object] = []
    used: list[bpy.types.Object] = []
    moving_mounts: set[bpy.types.Object] = set()
    for part in parts:
        slot = part["slot"]
        is_body = part["socket"] is None
        target = None
        if not is_body:
            host_sockets = sockets_by_slot.get(part["host"])
            if host_sockets is None:
                raise ValueError(f"slot '{slot}': host slot '{part['host']}' was not built before it")
            target = host_sockets.get(part["socket"])
            if target is None:
                raise ValueError(f"slot '{slot}': '{part['host']}' has no socket '{part['socket']}' "
                                 f"(available: {', '.join(sorted(host_sockets))})")
        result, objs, actions = (run_asset_part(part, palette) if "asset" in part
                                 else run_part(part, palette))
        if part_roots is not None:
            part_roots[slot] = result
        available = _socket_map(objs)
        if "asset" in part:
            names = {item["name"] for item in part["asset"]["interface"].get("sockets", [])}
            available = {name: obj for name, obj in available.items() if name in names}
        sockets_by_slot[slot] = available
        rename_part(slot, objs, actions, keep_sockets=is_body)
        bpy.context.view_layer.update()
        x, y, z = part.get("offset", (0.0, 0.0, 0.0))  # asset/glTF X-right, Y-up, Z-front
        shift = Matrix.Translation((x, -z, y))  # Blender is Z-up, with front at -Y
        base = target.matrix_world.copy() if target is not None else result.matrix_world.copy()
        result.matrix_world = shift @ base  # asset axes, independent of socket orientation
        # Explicit moving joints keep their mounted parts in the transform hierarchy.
        # Static sockets retain the original placement and cleanup behavior.
        follows_joint = follows_animation(target)
        if follows_joint:
            moving_mounts.add(target)
            result.parent = target
            result.matrix_parent_inverse = Matrix.Identity(4)
            result.matrix_world = shift @ base
        if target is not None:
            if target not in used:  # several slots may share one socket
                used.append(target)
            log(f"slot {slot}: {part['ref']} → {part['host']}.{part['socket']} offset={part.get('offset')}")
        if not follows_joint:
            tops.append(result)
        bpy.context.view_layer.update()
    expose_asset_sockets(recipe, sockets_by_slot, tops)
    for target in used:
        if target in moving_mounts:
            # An occupied animated mount is a joint, rather than an available socket.
            target.name = target.name.replace("socket_", "joint_", 1)
            for key in ("socket", "socket_type"):
                if key in target:
                    del target[key]
        else:
            bpy.data.objects.remove(target, do_unlink=True)
    return tops


def merge_animations(name: str = "work") -> list[str]:
    """Push every object's action into an NLA track `name`; the glTF exporter (NLA_TRACKS mode)
    merges same-named tracks into ONE animation. Returns names of animated objects."""
    animated: list[str] = []
    for obj in bpy.data.objects:
        data = obj.animation_data
        if data is None or data.action is None:
            continue
        track = data.nla_tracks.new()
        track.name = name
        track.strips.new(name, int(data.action.frame_range[0]), data.action)
        data.action = None
        animated.append(obj.name)
    return animated


def unit_animation_stats(root: bpy.types.Object) -> list[dict[str, Any]]:
    """Opt-in rigid-part clips already authored as NLA tracks by unit generators."""
    clips: dict[str, dict[str, Any]] = {}
    for obj in checks.hierarchy(root):
        data = obj.animation_data
        if data is None:
            continue
        for track in data.nla_tracks:
            for strip in track.strips:
                if not strip.action.get("unit_clip"):
                    continue
                name = track.name
                start, end = int(strip.frame_start), int(strip.frame_end)
                spec = clips.setdefault(name, {"name": name, "frames": [start, end], "nodes": 0,
                                                "loop": bool(strip.action.get("clip_loop", True)), "events": []})
                spec["frames"] = [min(spec["frames"][0], start), max(spec["frames"][1], end)]
                spec["nodes"] += 1
                for event in json.loads(strip.action.get("clip_events", "[]")):
                    if event not in spec["events"]:
                        spec["events"].append(event)
    for spec in clips.values():
        spec["seconds"] = round((spec["frames"][1] - spec["frames"][0]) / voxlib.FPS, 2)
    return list(clips.values())


def make_root(recipe: dict[str, Any], tops: list[bpy.types.Object]) -> bpy.types.Object:
    root_name = recipe["id"]
    existing = bpy.data.objects.get(root_name)
    if existing is not None:
        existing.name = f"{root_name}_geo"
    root = bpy.data.objects.new(root_name, None)
    root.name = root_name
    root.empty_display_type = "PLAIN_AXES"
    voxlib.link(root)
    bpy.context.view_layer.update()
    for obj in tops:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_world = world
    root["asset_id"] = recipe["id"]
    root["variant_id"] = recipe["variant"]
    root["hash"] = recipe["hash"]
    root["level"] = recipe["level"]
    root["kind"] = {"components": "component", "characters": "character"}.get(recipe["kind"], "asset")
    root["generator_version"] = recipe["generator_version"]
    return root


def add_collision(root: bpy.types.Object) -> bpy.types.Object:
    """Simplified collision: union of per-object world AABBs (contained boxes dropped)."""
    bpy.context.view_layer.update()
    boxes: list[tuple[Vector, Vector]] = []
    for obj in checks.visual_meshes(root):
        lo, hi = checks.world_bbox([obj])
        if (hi - lo).length > 0:
            boxes.append((lo, hi))
    boxes.sort(key=lambda b: -(b[1] - b[0]).length)
    kept: list[tuple[Vector, Vector]] = []
    for lo, hi in boxes:
        inside = any(all(k_lo[i] - 1e-4 <= lo[i] and hi[i] <= k_hi[i] + 1e-4 for i in range(3)) for k_lo, k_hi in kept)
        if not inside:
            kept.append((lo, hi))

    bm = bmesh.new()
    for lo, hi in kept:
        result = bmesh.ops.create_cube(bm, size=1.0)
        size, center = hi - lo, (lo + hi) / 2
        for v in result["verts"]:
            v.co = Vector((center.x + v.co.x * size.x, center.y + v.co.y * size.y, center.z + v.co.z * size.z))
    mesh = bpy.data.meshes.new(f"{root.name}-colonly")
    bm.to_mesh(mesh)
    bm.free()
    col = bpy.data.objects.new(f"{root.name}-colonly", mesh)
    voxlib.link(col, root)
    col.display_type = "WIRE"
    return col


def bake_outline_normals(root: bpy.types.Object) -> None:
    """Store smoothed (vertex-averaged) normals, octahedral-encoded in glTF space, as the 2nd UV map.

    Flat-shaded voxel meshes have split normals, so a hull outline pushed along NORMAL cracks at
    every corner. Engines read TEXCOORD_1 (Godot: UV2) instead — see toon_outline.gdshader.
    """
    for obj in checks.visual_meshes(root):
        mesh = obj.data
        while len(mesh.uv_layers) < 2:
            mesh.uv_layers.new(name="uv" if not mesh.uv_layers else "outline_nrm")
        layer = mesh.uv_layers[1]
        encoded = []
        for v in mesh.vertices:
            n = v.normal
            x, y, z = n.x, n.z, -n.y                      # Blender → glTF axes
            s = abs(x) + abs(y) + abs(z) or 1.0
            x, y, z = x / s, y / s, z / s
            if z < 0:
                x, y = (1 - abs(y)) * (1 if x >= 0 else -1), (1 - abs(x)) * (1 if y >= 0 else -1)
            encoded.append((x * 0.5 + 0.5, 1.0 - (y * 0.5 + 0.5)))   # exporter flips V
        data = [0.0] * (len(mesh.loops) * 2)
        for loop in mesh.loops:
            data[loop.index * 2:loop.index * 2 + 2] = encoded[loop.vertex_index]
        layer.data.foreach_set("uv", data)


def export_glb(path: Path, *, preserve_unit_clips: bool = False) -> None:
    bpy.context.scene.frame_set(0)
    options = {"export_optimize_animation_keep_anim_object": True} if preserve_unit_clips else {}
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=False,
        export_yup=True,
        export_apply=True,
        export_extras=True,
        export_normals=True,
        export_texcoords=True,
        export_materials="EXPORT",
        export_vertex_color="ACTIVE",
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_cameras=False,
        export_lights=False,
        **options,
    )


def check_exported_unit_clips(path: Path, clips: list[dict[str, Any]]) -> dict[str, Any]:
    """Check the exported artifact: constant idle/restore tracks must survive optimization."""
    data = path.read_bytes()
    length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError("GLB JSON chunk missing")
    document = json.loads(data[20:20 + length])
    exported = {clip["name"]: clip for clip in document.get("animations", [])}
    errors = []
    for spec in clips:
        clip = exported.get(spec["name"])
        if not clip or not clip.get("channels"):
            errors.append(f"{spec['name']}: missing channels")
            continue
        accessors = [document["accessors"][sampler["input"]] for sampler in clip["samplers"]]
        duration = max(a["max"][0] for a in accessors) - min(a["min"][0] for a in accessors)
        if abs(duration - spec["seconds"]) > .01:
            errors.append(f"{spec['name']}: duration {duration:.3f}s != {spec['seconds']}s")
    return {"name": "unit_clips", "ok": not errors,
            "message": "; ".join(errors) if errors else "exported clips: " + ", ".join(c["name"] for c in clips)}


# ---------------------------------------------------------------------- characters

def _clear_preview_rig() -> None:
    """preview.render adds a camera, a sun and a world per call; drop them before the next pass."""
    for obj in [o for o in bpy.data.objects if o.name.startswith("preview_")]:
        bpy.data.objects.remove(obj, do_unlink=True)


def build_character(recipe: dict[str, Any], args: argparse.Namespace, report: dict[str, Any]) -> None:
    """Armature + skinned meshes from the generator, one glTF clip per NLA track (no `work` merge),
    rest-pose checks and model-sheet previews, plus a posed 3/4 preview for catalogue cards."""
    import humanoid

    rig_obj, _objects, _actions = run_part(recipe["parts"][0], recipe["palette"]["colors"])
    root = make_root(recipe, [rig_obj])
    rigs = checks.armatures(root)
    rig = rigs[0] if rigs else None
    tracks = list(rig.animation_data.nla_tracks) if rig is not None and rig.animation_data else []
    if rig is not None:
        rig.data.pose_position = "REST"
    scene = bpy.context.scene
    scene.frame_end = max((int(s.frame_end) for t in tracks for s in t.strips), default=0)
    scene.frame_set(0)
    bpy.context.view_layer.update()

    results, stats = checks.run(root, recipe, recipe["palette"]["colors"])
    results += checks.character(root, recipe, list(humanoid.REQUIRED_BONES))
    stats["animations"] = [{"name": t.name, "frames": [int(s.frame_start), int(s.frame_end)],
                            "seconds": round((s.frame_end - s.frame_start) / voxlib.FPS, 2)}
                           for t in tracks for s in list(t.strips)[:1]]
    stats["rig"] = {"name": humanoid.RIG, "bones": len(rig.data.bones) if rig is not None else 0}
    report["checks"], report["stats"] = results, stats
    for c in results:
        log(f"check {c['name']:<14} {'PASS' if c['ok'] else 'FAIL'}  {c['message']}")

    bake_outline_normals(root)
    if rig is not None:
        rig.data.pose_position = "POSE"
    export_glb(args.out / "model.glb")
    log(f"exported {args.out / 'model.glb'} with clips {[t.name for t in tracks]}")

    if not args.no_preview:
        if rig is not None:
            rig.data.pose_position = "REST"
        bpy.context.view_layer.update()
        lo, hi = checks.world_bbox(checks.visual_meshes(root))
        size = int(recipe["preview"]["size"])
        files = preview.render(args.out, size, lo, hi, [], views=preview.CHARACTER_VIEWS)
        if rig is not None and any(t.name == "idle" for t in tracks):
            _clear_preview_rig()
            rig.data.pose_position = "POSE"
            for t in tracks:
                t.mute = t.name != "idle"
            scene.frame_set(12)
            bpy.context.view_layer.update()
            files.update(preview.render(args.out, size, lo, hi, [], views={"pose": preview.CHARACTER_VIEWS["34"]}))
            for t in tracks:
                t.mute = False
        report["previews"] = files

    report["status"] = "ok" if all(c["ok"] for c in results) else "failed"
    if report["status"] != "ok":
        report["error"] = "checks failed: " + ", ".join(c["name"] for c in results if not c["ok"])


# ---------------------------------------------------------------------- main

class _Done(Exception):
    """Early successful exit (material builds skip geometry export)."""


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"status": "failed", "error": None, "checks": [], "stats": {},
                              "blender_version": bpy.app.version_string}
    code = 0
    try:
        recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
        report.update({"kind": recipe["kind"], "id": recipe["id"], "variant": recipe["variant"],
                       "hash": recipe["hash"], "level": recipe["level"]})
        if recipe["kind"] == "components":
            report["structure"] = {"status": "not_run", "issues": [], "verified": []}
        elif "composition" in recipe:
            report["composition"] = recipe["composition"]
        reset_scene()
        voxlib.configure_surfaces(recipe.get("palette", {}))
        if args.save_blend is not None:
            seed_blend(recipe, args.save_blend)
            report["status"] = "ok"
            raise _Done()
        if recipe["kind"] == "characters":
            build_character(recipe, args, report)
            raise _Done()
        if recipe["kind"] == "materials":
            results, stats, files = material_build.run(recipe, args.out, log)
            report.update({"checks": results, "stats": stats, "previews": files,
                           "status": "ok" if all(c["ok"] for c in results) else "failed"})
            if report["status"] != "ok":
                report["error"] = "checks failed: " + ", ".join(c["name"] for c in results if not c["ok"])
            raise _Done()
        report["parts"] = [{"slot": p["slot"], "ref": p["ref"], "host": p.get("host"),
                            "socket": p["socket"], "offset": p.get("offset", (0, 0, 0))}
                           for p in recipe["parts"]]
        tops = assemble(recipe)
        root = make_root(recipe, tops)
        collision = add_collision(root)
        bpy.context.view_layer.update()

        frame_end = max((int(a.frame_range[1]) for a in bpy.data.actions), default=0)
        bpy.context.scene.frame_end = frame_end
        bpy.context.scene.frame_set(0)

        results, stats = checks.run(root, recipe, recipe["palette"]["colors"])
        if recipe["kind"] == "components":
            report["structure"] = stats.pop("structure")
        animated = merge_animations("work")
        stats["animations"] = ([{"name": "work", "frames": [0, frame_end], "seconds": round(frame_end / voxlib.FPS, 2),
                                 "nodes": len(animated)}] if animated else [])
        unit_clips = unit_animation_stats(root)
        if unit_clips:
            stats["animations"] += unit_clips
        report["checks"], report["stats"] = results, stats
        for c in results:
            log(f"check {c['name']:<10} {'PASS' if c['ok'] else 'FAIL'}  {c['message']}")
        if animated:
            log(f"animation 'work': {len(animated)} animated nodes, {frame_end} frames")

        bake_outline_normals(root)
        export_glb(args.out / "model.glb", preserve_unit_clips=bool(unit_clips))
        log(f"exported {args.out / 'model.glb'}")
        if unit_clips:
            result = check_exported_unit_clips(args.out / "model.glb", unit_clips)
            results.append(result)
            log(f"check unit_clips {'PASS' if result['ok'] else 'FAIL'} {result['message']}")

        if not args.no_preview:
            lo, hi = checks.world_bbox(checks.visual_meshes(root))
            hidden = [collision, *checks.sockets(root)]
            report["previews"] = preview.render(args.out, int(recipe["preview"]["size"]), lo, hi, hidden)

        report["status"] = "ok" if all(c["ok"] for c in results) else "failed"
        if report["status"] != "ok":
            report["error"] = "checks failed: " + ", ".join(c["name"] for c in results if not c["ok"])
    except _Done:
        pass
    except Exception as exc:  # report every failure; never fail silently
        traceback.print_exc()
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    report["builder_duration_s"] = round(time.monotonic() - started, 2)
    (args.out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"status {report['status']} in {report['builder_duration_s']}s")
    return code


if __name__ == "__main__":
    sys.exit(main())
