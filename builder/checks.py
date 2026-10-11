"""Post-build validation of the assembled model (runs inside Blender)."""

from __future__ import annotations

import math
from typing import Any

import bpy
from mathutils import Vector

from structure import Box, validate as validate_structure

Check = dict[str, Any]


def is_collision(obj: bpy.types.Object) -> bool:
    return obj.name.endswith("-colonly")


def hierarchy(root: bpy.types.Object) -> list[bpy.types.Object]:
    return [root, *root.children_recursive]


def visual_meshes(root: bpy.types.Object) -> list[bpy.types.Object]:
    return [o for o in hierarchy(root) if o.type == "MESH" and not is_collision(o)]


def sockets(root: bpy.types.Object) -> list[bpy.types.Object]:
    return [o for o in hierarchy(root) if o.type == "EMPTY" and o.name.startswith("socket_")]


def to_yup(v: Vector | tuple[float, float, float]) -> list[float]:
    """Blender (x, y, z-up) → glTF (x, y-up, z)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4) + 0.0]


def world_bbox(objs: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        mw = ev.matrix_world
        for v in mesh.vertices:
            co = mw @ v.co
            lo = Vector(map(min, lo, co))
            hi = Vector(map(max, hi, co))
        ev.to_mesh_clear()
    if math.isinf(lo.x):
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return lo, hi


def _check(name: str, ok: bool, message: str) -> Check:
    return {"name": name, "ok": bool(ok), "message": message}


def run(root: bpy.types.Object, recipe: dict[str, Any], palette_hex: dict[str, str]) -> tuple[list[Check], dict[str, Any]]:
    interface = recipe["interface"]
    vs = float(interface["voxel_size"])
    tol = float(recipe["limits"]["bbox_tolerance"])
    meshes = visual_meshes(root)
    results: list[Check] = []

    # --- bbox / pivot -------------------------------------------------------
    lo, hi = world_bbox(meshes)
    dims_b = hi - lo
    dims = [round(dims_b.x, 4), round(dims_b.z, 4), round(dims_b.y, 4)]  # Y-up order
    envelope = [round(g * vs, 4) for g in interface["grid_size"]]
    over = [f"{'XYZ'[i]} {d:.3f} > {e:.3f}" for i, (d, e) in enumerate(zip(dims, envelope)) if d > e + tol]
    results.append(_check("bbox", not over and meshes,
                          f"{dims} m within grid {interface['grid_size']}×{vs} = {envelope} m" if not over
                          else "exceeds envelope: " + ", ".join(over)))
    in_footprint = lo.x - tol <= 0 <= hi.x + tol and lo.y - tol <= 0 <= hi.y + tol
    if interface.get("pivot") == "ground":
        pivot_ok = lo.z >= -tol and in_footprint
        results.append(_check("pivot", pivot_ok,
                              f"ground: origin under the model, lowest point {lo.z:.3f} m above ground" if pivot_ok
                              else f"model must not go below y=0 and stay around the origin (min height {lo.z:.3f} m)"))
    else:
        pivot_ok = abs(lo.z) <= tol and in_footprint
        results.append(_check("pivot", pivot_ok,
                              f"bottom_center: min height {lo.z:.3f} m, origin inside footprint" if pivot_ok
                              else f"model must stand on y=0 around the origin (min height {lo.z:.3f} m)"))

    # --- polycount / geometry ------------------------------------------------
    depsgraph = bpy.context.evaluated_depsgraph_get()
    polys = tris = verts = degenerate = nan_normals = 0
    palette_bytes = {tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in palette_hex.values()}
    off_palette: set[tuple[int, int, int]] = set()
    uncolored: list[str] = []
    for obj in meshes:
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        polys += len(mesh.polygons)
        verts += len(mesh.vertices)
        for poly in mesh.polygons:
            tris += len(poly.vertices) - 2
            if poly.area < 1e-10:
                degenerate += 1
            if any(math.isnan(c) for c in poly.normal):
                nan_normals += 1
        attr = mesh.color_attributes.get("Color")
        if attr is None or len(mesh.loops) == 0:
            uncolored.append(obj.name)
        else:
            flat = [0.0] * (len(attr.data) * 4)
            attr.data.foreach_get("color_srgb", flat)
            for i in range(0, len(flat), 4):
                rgb = (round(flat[i] * 255), round(flat[i + 1] * 255), round(flat[i + 2] * 255))
                if rgb not in palette_bytes and not any(
                        all(abs(a - b) <= 1 for a, b in zip(rgb, p)) for p in palette_bytes):
                    off_palette.add(rgb)
        ev.to_mesh_clear()

    limit = int(recipe["limits"]["polys"])
    results.append(_check("polycount", 0 < polys <= limit, f"{polys} faces ({tris} tris), limit {limit}"))
    geo_ok = degenerate == 0 and nan_normals == 0 and polys > 0
    results.append(_check("geometry", geo_ok,
                          "no degenerate faces, normals finite" if geo_ok
                          else f"{degenerate} degenerate faces, {nan_normals} NaN normals, {polys} faces"))

    # --- sockets ---------------------------------------------------------------
    present = {o.name[len("socket_"):] for o in sockets(root)}
    required = [s["name"] for s in interface.get("sockets", [])]
    missing = [n for n in required if n not in present]
    results.append(_check("sockets", not missing,
                          f"{len(required)} required present ({', '.join(required) or 'none'})" if not missing
                          else f"missing: {', '.join(missing)}"))

    # --- palette -----------------------------------------------------------------
    palette_ok = not off_palette and not uncolored
    hexes = ", ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in sorted(off_palette)[:8])
    results.append(_check("palette", palette_ok,
                          "all vertex colors from palette.yaml" if palette_ok
                          else (f"off-palette colors: {hexes}. " if off_palette else "")
                          + (f"no vertex colors on: {', '.join(uncolored)}" if uncolored else "")))

    # --- component structure (opt-in) ----------------------------------------
    if recipe["kind"] == "components":
        intent = recipe.get("design_intent")
        declared = set(intent.get("primary_parts", []) + intent.get("secondary_parts", [])) if intent else set()
        boxes: list[Box] = []
        if intent:
            for obj in meshes:
                part = str(obj.get("semantic_part", ""))
                if not part:
                    # Exact mesh names may stand in for labels; prefixes cannot because they
                    # silently misclassify stray geometry as part of a declared group.
                    name = obj.name.rsplit(".", 1)[0] if obj.name.rsplit(".", 1)[-1].isdigit() else obj.name
                    if name in declared:
                        part = name
                obj_lo, obj_hi = world_bbox([obj])
                boxes.append(Box(obj.name, part,
                                 (obj_lo.x, obj_lo.z, -obj_hi.y),
                                 (obj_hi.x, obj_hi.z, -obj_lo.y)))
        structure = validate_structure(intent, boxes, int(recipe["level"]))
        if intent:
            issue_count = len(structure["issues"])
            results.append(_check("structure", structure["status"] == "ok",
                                  f"{len(structure['verified'])} relations verified, {issue_count} issues"))

    stats = {
        "faces": polys,
        "tris": tris,
        "verts": verts,
        "objects": len(hierarchy(root)),
        "bbox_m": dims,
        "bbox_vox": [round(d / vs, 2) for d in dims],
        "envelope_m": envelope,
        "sockets": [{"name": o.name[len("socket_"):], "position": to_yup(o.matrix_world.translation)}
                    for o in sockets(root)],
        "animations": [{"name": a.name, "frames": [int(a.frame_range[0]), int(a.frame_range[1])]}
                       for a in bpy.data.actions if a.users > 0],
    }
    if recipe["kind"] == "components":
        stats["structure"] = structure
    return results, stats


# ---------------------------------------------------------------------------------- characters
def armatures(root: bpy.types.Object) -> list[bpy.types.Object]:
    return [o for o in hierarchy(root) if o.type == "ARMATURE"]


def character(root: bpy.types.Object, recipe: dict[str, Any], required_bones: list[str]) -> list[Check]:
    """Rig, skinning and clip checks for a character build (run in the rest pose)."""
    spec = recipe["character"]
    tol = float(recipe["limits"]["bbox_tolerance"])
    results: list[Check] = []
    arms = armatures(root)
    arm = arms[0] if len(arms) == 1 else None
    results.append(_check("armature", arm is not None,
                          f"one armature '{arm.name}' ({arm.get('rig', '?')})" if arm is not None
                          else f"expected exactly one armature, found {len(arms)}"))
    if arm is None:
        return results
    bones = {b.name for b in arm.data.bones}
    missing = [b for b in required_bones if b not in bones]
    results.append(_check("required_bones", not missing,
                          f"{len(required_bones)} humanoid bones present" if not missing
                          else "missing bones: " + ", ".join(missing)))

    unweighted = 0
    no_modifier: list[str] = []
    stray: set[str] = set()
    total = 0
    for obj in visual_meshes(root):
        if not any(m.type == "ARMATURE" and m.object == arm for m in obj.modifiers):
            no_modifier.append(obj.name)
            continue
        names = {g.index: g.name for g in obj.vertex_groups}
        stray |= {n for n in names.values() if n not in bones}
        for v in obj.data.vertices:
            total += 1
            if sum(g.weight for g in v.groups if names.get(g.group) in bones) < 0.99:
                unweighted += 1
    ok = not no_modifier and not stray and unweighted == 0
    results.append(_check("skin_weights", ok,
                          f"{total} vertices skinned to the rig, every vertex fully weighted" if ok else
                          "; ".join(filter(None, [
                              f"not skinned: {', '.join(no_modifier)}" if no_modifier else "",
                              f"groups without a bone: {', '.join(sorted(stray))}" if stray else "",
                              f"{unweighted} vertices without full weight" if unweighted else ""]))))

    tracks = {t.name: t for t in (arm.animation_data.nla_tracks if arm.animation_data else [])}
    missing_clips = [c for c in spec["clips"] if c not in tracks or not tracks[c].strips]
    broken: list[str] = []
    for name, track in tracks.items():
        action = track.strips[0].action if track.strips else None
        if action is None:
            continue
        from voxlib import iter_fcurves
        for fc in iter_fcurves(action):
            keys = fc.keyframe_points
            if len(keys) > 1 and abs(keys[0].co[1] - keys[-1].co[1]) > 1e-3:
                broken.append(f"{name}:{fc.data_path}[{fc.array_index}]")
                break
    ok = not missing_clips and not broken
    results.append(_check("animations", ok,
                          f"clips {', '.join(spec['clips'])} present and loop seamlessly" if ok else
                          "; ".join(filter(None, [f"missing clips: {', '.join(missing_clips)}" if missing_clips else "",
                                                  f"not looping: {', '.join(broken)}" if broken else ""]))))

    lo, _hi = world_bbox(visual_meshes(root))
    grounded = abs(lo.z) <= tol
    results.append(_check("grounded", grounded,
                          f"feet on the ground plane (lowest point {lo.z:.3f} m)" if grounded
                          else f"lowest point {lo.z:.3f} m: the feet must stand on z = 0"))
    return results
