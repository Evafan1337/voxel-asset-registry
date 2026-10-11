"""Reference Lab (runs inside Blender): study external character meshes and turn one into a template.

    blender -b --factory-startup <source.blend> --python-exit-code 1 -P builder/reference_lab.py -- build --job job.json
    blender -b --factory-startup <normalized.blend> --python-exit-code 1 -P builder/reference_lab.py -- template --job job.json

`build` never saves the opened source file: it writes analysis.json, normalized/normalized.blend (+ .glb for
the web viewer), standard previews and — when the reference has a semantic mapping — its regions.
`template` reads the normalized mesh and writes builder/character_templates/<kind>/<id>/ (template.blend,
template.json, template.glb, preview.png). The job file is written by backend/references.py, which also
checks the reference permissions before a template is extracted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import chartemplate as ct  # noqa: E402
import humanoid as hu  # noqa: E402
import preview  # noqa: E402

GEOMETRY = {"MESH"}
WIRE_VIEWS = ("front", "34", "side")
# Fixed frame for reference previews: a 1.75 m character with arms out (T-pose) fits, so every
# reference and template is rendered at the same scale as the others.
STANDARD_FRAME = (Vector((-0.9, -0.45, 0.0)), Vector((0.9, 0.45, 1.95)))
SKIN = (0.78, 0.62, 0.52, 1.0)
REGION_COLORS = {
    "head": "#e8c9a8", "cranium": "#d9b48f", "forehead": "#f0d2b0", "brow": "#b07a4f", "eye_region": "#5aa6d6",
    "cheek": "#f29c8f", "nose": "#e0605a", "jaw": "#c98b6b", "chin": "#9e6a4f", "ear": "#b58ad6",
    "neck": "#cfa57f", "chest": "#4f8fd6", "waist": "#6fb3a0", "pelvis": "#8f6fd6", "shoulder": "#f2b84b",
    "upper_arm": "#e87f4f", "elbow": "#c84f4f", "forearm": "#e8a04f", "hand": "#f2d64b", "thigh": "#4fd67a",
    "knee": "#2f9e5a", "shin": "#7ad6c8", "calf": "#4fb3d6", "ankle": "#2f7a9e", "foot": "#3f5fd6",
}


def log(message: str) -> None:
    print(f"[reflab] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="reference_lab.py")
    p.add_argument("mode", choices=["build", "template"])
    p.add_argument("--job", required=True, type=Path)
    return p.parse_args(argv)


def hex_rgba(value: str) -> tuple[float, float, float, float]:
    v = value.lstrip("#")
    srgb = [int(v[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (lin[0], lin[1], lin[2], 1.0)


# ---------------------------------------------------------------------------------- analysis
def mesh_objects() -> list[bpy.types.Object]:
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


def analyze() -> dict[str, Any]:
    """Everything a human needs to judge the file: objects, topology, materials, rig, clips, size."""
    objects, meshes, arms = [], [], []
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for obj in bpy.data.objects:
        objects.append({"name": obj.name, "type": obj.type, "parent": obj.parent.name if obj.parent else None,
                        "location": [round(c, 4) for c in obj.location],
                        "rotation_deg": [round(math.degrees(c), 2) for c in obj.rotation_euler],
                        "scale": [round(c, 4) for c in obj.scale],
                        "hidden": bool(obj.hide_render or obj.hide_viewport)})
        if obj.type == "MESH":
            m = obj.data
            ngons = Counter(len(p.vertices) for p in m.polygons)
            bm = bmesh.new()
            bm.from_mesh(m)
            boundary = sum(1 for e in bm.edges if e.is_boundary)
            nonmanifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
            volume = signed_volume(bm)
            bm.free()
            groups = {g.index: g.name for g in obj.vertex_groups}
            per_vertex = [len([g for g in v.groups if g.weight > 1e-4]) for v in m.vertices]
            weighted = sum(1 for n in per_vertex if n)
            for v in m.vertices:
                p = obj.matrix_world @ v.co
                lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
                hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
            meshes.append({
                "object": obj.name, "mesh": m.name, "vertices": len(m.vertices), "edges": len(m.edges),
                "faces": len(m.polygons), "triangles": sum(len(p.vertices) - 2 for p in m.polygons),
                "face_sides": {str(k): v for k, v in sorted(ngons.items())},
                "boundary_edges": boundary, "nonmanifold_edges": nonmanifold,
                "normals": "inward (flipped)" if volume < 0 else "outward", "signed_volume": round(volume, 5),
                "uv_layers": [u.name for u in m.uv_layers], "color_attributes": [a.name for a in m.color_attributes],
                "materials": [s.material.name if s.material else None for s in obj.material_slots],
                "vertex_groups": list(groups.values()),
                "weights": {"weighted_vertices": weighted, "max_influences": max(per_vertex, default=0),
                            "mean_influences": round(sum(per_vertex) / max(len(per_vertex), 1), 2)},
                "modifiers": [{"name": md.name, "type": md.type,
                               "object": getattr(getattr(md, "object", None), "name", None)} for md in obj.modifiers],
                "shape_keys": [k.name for k in m.shape_keys.key_blocks] if m.shape_keys else [],
                "dimensions": [round(c, 4) for c in obj.dimensions],
            })
        if obj.type == "ARMATURE":
            arms.append({"object": obj.name, "bones": [{"name": b.name, "parent": b.parent.name if b.parent else None,
                                                         "head": [round(c, 4) for c in b.head_local],
                                                         "tail": [round(c, 4) for c in b.tail_local]}
                                                        for b in obj.data.bones]})
    actions = [{"name": a.name, "frames": [round(a.frame_range[0], 2), round(a.frame_range[1], 2)],
                "users": a.users} for a in bpy.data.actions]
    totals = {k: sum(m[k] for m in meshes) for k in ("vertices", "edges", "faces", "triangles")}
    size = (hi - lo) if not math.isinf(lo.x) else Vector()
    return {
        "blender_version": bpy.app.version_string, "file_version": ".".join(str(v) for v in bpy.data.version),
        "objects": objects, "meshes": meshes, "armatures": arms, "animations": actions,
        "materials": [m.name for m in bpy.data.materials],
        "totals": {**totals, "objects": len(objects), "meshes": len(meshes), "armatures": len(arms),
                   "bones": sum(len(a["bones"]) for a in arms), "animations": len(actions),
                   "materials": len(bpy.data.materials),
                   "vertex_groups": sum(len(m["vertex_groups"]) for m in meshes)},
        "bbox": {"min": [round(c, 4) for c in lo], "max": [round(c, 4) for c in hi]} if meshes else None,
        "dimensions": [round(c, 4) for c in size] if meshes else None,
    }


# ---------------------------------------------------------------------------------- normalization
def _feet_forward(points: list[Vector], lo: float, height: float) -> Vector:
    feet = [p for p in points if p.z < lo + 0.04 * height]
    shins = [p for p in points if lo + 0.12 * height < p.z < lo + 0.25 * height]
    if not feet or not shins:
        return Vector((0, 0, 0))
    f = sum(feet, Vector()) / len(feet)
    s = sum(shins, Vector()) / len(shins)
    return Vector((f.x - s.x, f.y - s.y, 0.0))


def normalize(objs: list[bpy.types.Object], target_height: float) -> dict[str, Any]:
    """Bake transforms, stand on z = 0, centre X/Y, scale to `target_height`, turn the toes to −Y.
    Topology, UVs, normals, vertex groups and weights are left as they are."""
    rigs = {md.object for o in objs for md in o.modifiers if md.type == "ARMATURE" and md.object}
    for rig in rigs:
        rig.data.pose_position = "REST"
    for obj in objs:
        for md in [m for m in obj.modifiers if m.type == "ARMATURE" and m.object is None]:
            obj.modifiers.remove(md)                                    # an empty armature modifier does nothing
        for md in [m for m in obj.modifiers if m.type == "MIRROR"]:     # half-mesh authoring is part of the shape
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=md.name)
    bpy.context.view_layer.update()
    for obj in objs:
        mw = obj.matrix_world.copy()
        if obj.parent is not None:
            obj.parent = None
        obj.data.transform(mw)
        obj.matrix_world = Matrix.Identity(4)
    points = [v.co.copy() for o in objs for v in o.data.vertices]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    height = hi.z - lo.z
    toes = _feet_forward(points, lo.z, height)
    turn = 0.0
    if toes.length > 0.01 * height:
        angle = math.atan2(toes.x, -toes.y)                            # 0 when the toes already point to −Y
        turn = round(angle / (math.pi / 2)) * (math.pi / 2)
    rot = Matrix.Rotation(-turn, 4, "Z")
    for obj in objs:
        obj.data.transform(rot)
    points = [v.co.copy() for o in objs for v in o.data.vertices]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    k = target_height / (hi.z - lo.z)
    shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    norm = Matrix.Diagonal((k, k, k, 1.0)) @ Matrix.Translation(shift)
    for obj in objs:
        obj.data.transform(norm)
        obj.data.update()
    for rig in rigs:
        rig.matrix_world = norm @ rot @ rig.matrix_world
    points = [v.co for o in objs for v in o.data.vertices]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return {"source_height": round(height, 5), "scale": round(k, 6), "turn_deg": round(math.degrees(turn), 1),
            "offset": [round(c, 5) for c in shift], "height": round(hi.z - lo.z, 5),
            "bbox": {"min": [round(c, 4) for c in lo], "max": [round(c, 4) for c in hi]},
            "front": "-Y", "objects": [o.name for o in objs], "rigs": [r.name for r in rigs]}


def keep_only(objs: list[bpy.types.Object]) -> None:
    keep = set(objs)
    for obj in objs:
        for md in obj.modifiers:
            if md.type == "ARMATURE" and md.object:
                keep.add(md.object)
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        if action.users == 0:
            bpy.data.actions.remove(action)
    bpy.data.orphans_purge(do_recursive=True)


def ensure_material(objs: list[bpy.types.Object]) -> None:
    for obj in objs:
        if obj.material_slots and any(s.material for s in obj.material_slots):
            continue
        mat = bpy.data.materials.get("reference_skin") or bpy.data.materials.new("reference_skin")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = SKIN
        mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
        obj.data.materials.append(mat)


def export_glb(path: Path, objs: list[bpy.types.Object], *, colors: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in objs or any(md.type == "ARMATURE" and md.object == obj for o in objs for md in o.modifiers))
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=False, export_animations=False, export_cameras=False, export_lights=False,
                              export_extras=False, export_materials="EXPORT", export_normals=True,
                              export_vertex_color="ACTIVE" if colors else "NONE", export_skins=True)


def _clear_preview_rig() -> None:
    for obj in [o for o in bpy.data.objects if o.name.startswith("preview_")]:
        bpy.data.objects.remove(obj, do_unlink=True)


def render_previews(out: Path, objs: list[bpy.types.Object], prefix: str = "", size: int = 512,
                    views: tuple[str, ...] = ("front", "34", "side", "back"), wire: bool = True) -> dict[str, str]:
    """Solid views and solid + wire views at the standard character camera and a fixed frame."""
    out.mkdir(parents=True, exist_ok=True)
    lo, hi = STANDARD_FRAME
    files: dict[str, str] = {}
    solid = preview.render(out, size, lo, hi, [], views={k: preview.CHARACTER_VIEWS[k] for k in views},
                           prefix=prefix)
    files.update({f"{prefix}{k}": v for k, v in solid.items()})
    if wire:
        _clear_preview_rig()
        wires = []
        mat = bpy.data.materials.get("preview_wire") or bpy.data.materials.new("preview_wire")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1)
        for obj in objs:
            w = obj.copy()
            w.data = obj.data.copy()
            w.name = f"wire_{obj.name}"
            bpy.context.scene.collection.objects.link(w)
            for md in list(w.modifiers):
                if md.type != "ARMATURE":
                    w.modifiers.remove(md)
            md = w.modifiers.new("wire", "WIREFRAME")
            md.thickness = 0.004
            md.use_replace = True
            md.use_even_offset = False
            w.data.materials.clear()
            w.data.materials.append(mat)
            wires.append(w)
        got = preview.render(out, size + 256, lo, hi, [],
                             views={k: preview.CHARACTER_VIEWS[k] for k in WIRE_VIEWS}, prefix=f"{prefix}wire_")
        files.update({f"{prefix}wire_{k}": v for k, v in got.items()})
        for w in wires:
            bpy.data.objects.remove(w, do_unlink=True)
    _clear_preview_rig()
    return files


# ---------------------------------------------------------------------------------- semantics
def combined_mesh(objs: list[bpy.types.Object]) -> tuple[list[ct.Vec], list[list[int]]]:
    verts: list[ct.Vec] = []
    faces: list[list[int]] = []
    for obj in objs:
        base = len(verts)
        verts += [tuple(obj.matrix_world @ v.co) for v in obj.data.vertices]
        faces += [[base + i for i in p.vertices] for p in obj.data.polygons]
    return verts, faces


def color_by_regions(obj: bpy.types.Object, regions: list[str]) -> None:
    mesh = obj.data
    for attr in list(mesh.color_attributes):
        mesh.color_attributes.remove(attr)
    col = mesh.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
    data = []
    for poly in mesh.polygons:
        names = Counter(ct.region_base(regions[i]) for i in poly.vertices)
        name = names.most_common(1)[0][0]
        rgba = hex_rgba(REGION_COLORS.get(name, "#aaaaaa"))
        srgb = [c ** (1 / 2.2) for c in rgba[:3]]
        for _ in poly.loop_indices:
            data.extend((*srgb, 1.0))
    col.data.foreach_set("color_srgb", data)
    mesh.color_attributes.active_color = col
    mat = bpy.data.materials.get("region_colors") or bpy.data.materials.new("region_colors")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    attr = nodes.get("Color Attribute") or nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Color"
    links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    mesh.materials.clear()
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = False


def semantic_study(job: dict[str, Any], objs: list[bpy.types.Object], ref_dir: Path) -> dict[str, Any]:
    """Regions + landmarks of the normalized reference from semantic.yaml (read by the backend)."""
    sem = ct.Semantic.from_dict(job["semantic"])
    verts, faces = combined_mesh(objs)
    weights, regions, chains = ct.classify(verts, sem)
    regions = ct.apply_overrides(ct.face_regions(verts, regions, sem), sem)
    lm = ct.find_landmarks(verts, chains, regions, sem)
    points = ct.evaluate(lm, verts)
    tmp = bpy.data.objects.new("regions", bpy.data.meshes.new("regions"))
    tmp.data.from_pydata(verts, [], faces)
    bpy.context.scene.collection.objects.link(tmp)
    color_by_regions(tmp, regions)
    hidden = [o for o in objs]
    for o in hidden:
        o.hide_render = True
    export_glb(ref_dir / "normalized" / "regions.glb", [tmp], colors=True)
    files = render_previews(ref_dir / "previews", [tmp], prefix="regions_", views=("front", "34", "side"),
                            wire=False)
    for o in hidden:
        o.hide_render = False
    bpy.data.objects.remove(tmp, do_unlink=True)
    counts = Counter(regions)
    return {"regions": regions, "chains": chains, "counts": dict(sorted(counts.items())),
            "landmarks": {k: [round(c, 4) for c in v] for k, v in points.items()},
            "landmark_vertices": {k: sorted(v) for k, v in lm.items()},
            "max_influences": max(len(w) for w in weights), "previews": files}


def run_build(job: dict[str, Any]) -> dict[str, Any]:
    ref_dir = Path(job["ref_dir"])
    report: dict[str, Any] = {"analysis": analyze()}
    objs = mesh_objects()
    if not objs:
        raise ValueError("no visible mesh objects in the reference")
    report["normalization"] = normalize(objs, float(job.get("target_height", 1.75)))
    keep_only(objs)
    out = ref_dir / "normalized"
    out.mkdir(parents=True, exist_ok=True)
    for obj in objs:
        obj["reference_id"] = job["reference_id"]
    bpy.context.scene["reference_normalization"] = json.dumps(report["normalization"])
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "normalized.blend"), copy=True, compress=True)
    log(f"saved {out / 'normalized.blend'}")
    ensure_material(objs)
    export_glb(out / "normalized.glb", objs)
    report["previews"] = render_previews(ref_dir / "previews", objs)
    if job.get("semantic"):
        study = semantic_study(job, objs, ref_dir)
        (ref_dir / "semantic.json").write_text(json.dumps({k: v for k, v in study.items() if k != "previews"},
                                                          ensure_ascii=False), encoding="utf-8")
        report["previews"].update(study["previews"])
        report["semantic"] = {"counts": study["counts"], "landmarks": study["landmarks"],
                              "max_influences": study["max_influences"]}
    return report


# ---------------------------------------------------------------------------------- template extraction
def signed_volume(bm: bmesh.types.BMesh) -> float:
    vol = 0.0
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        for k in range(1, len(vs) - 1):
            vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6
    return vol


def _repair(bm: bmesh.types.BMesh) -> dict[str, Any]:
    """Weld exact duplicates, close small holes, wind every face outward (the builder offsets garments
    along normals and Godot culls back faces — an inside-out source must not stay inside-out)."""
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    welded = before - len(bm.verts)
    holes = [e for e in bm.edges if e.is_boundary]
    filled = 0
    if holes:
        res = bmesh.ops.holes_fill(bm, edges=holes, sides=8)
        filled = len(res["faces"])
    vol_before = signed_volume(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if signed_volume(bm) < 0:                     # recalc keeps a closed mesh consistent; make it outward
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return {"welded_vertices": welded, "boundary_edges_before": len(holes), "filled_faces": filled,
            "boundary_edges_after": sum(1 for e in bm.edges if e.is_boundary),
            "normals": "flipped outward" if vol_before < 0 else "outward", "volume_m3": round(signed_volume(bm), 5)}


def _support_loops(bm: bmesh.types.BMesh, sem: ct.Semantic) -> list[dict[str, Any]]:
    """Add edge loops inside long limb segments (mid upper arm, mid forearm, mid thigh): better bends,
    and garment ends (short sleeves, rolled sleeves, shorts) get an edge to stop on."""
    P = sem.planes
    done = []
    specs = {"upper_arm": (0, P["shoulder"], P["elbow"]), "forearm": (0, P["elbow"], P["wrist"]),
             "thigh": (2, P["knee"], P["hip"])}
    for name, value in sem.support_loops.items():
        if name not in specs:
            continue
        axis, a, b = specs[name]
        a, b = a - 0.05, b + 0.05              # the plane only cuts faces it crosses: a loose range is safe
        for sign in ((1, -1) if axis == 0 else (1, -1)):
            def inside(v: bmesh.types.BMVert) -> bool:
                c = v.co[axis] * (sign if axis == 0 else 1)
                if axis == 0:
                    return a - 1e-4 <= c <= b + 1e-4 and v.co.z > sem.armpit - 0.05
                return a - 1e-4 <= c <= b + 1e-4 and v.co.x * sign > 0.012
            faces = [f for f in bm.faces if all(inside(v) for v in f.verts)]
            if not faces:
                continue
            geom = list({e for f in faces for e in f.edges}) + faces + list({v for f in faces for v in f.verts})
            co = Vector((sign * value, 0, 0)) if axis == 0 else Vector((0, 0, value))
            no = Vector((1, 0, 0)) if axis == 0 else Vector((0, 0, 1))
            res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, dist=1e-4)
            cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMVert)]
            done.append({"loop": name, "side": "L" if sign > 0 else "R", "at": value, "vertices": len(cut)})
    bm.verts.index_update()
    bm.faces.index_update()
    return done


def build_rig(name: str, joints: dict[str, tuple[ct.Vec, ct.Vec]]) -> bpy.types.Object:
    data = bpy.data.armatures.new(hu.RIG)
    rig = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for bone_name, parent, connected in hu.BONES:
        bone = data.edit_bones.new(bone_name)
        bone.head, bone.tail = joints[bone_name]
        if parent:
            bone.parent = data.edit_bones[parent]
            bone.use_connect = connected
    bpy.ops.object.mode_set(mode="OBJECT")
    data.display_type = "STICK"
    rig["rig"] = hu.RIG
    return rig


def template_skeleton(joints: dict[str, ct.Vec], b0: hu.Body) -> dict[str, tuple[ct.Vec, ct.Vec]]:
    """humanoid_v1 bones placed on the template's own joints (for weight painting and the Lab viewer)."""
    sk = hu.skeleton(b0)
    for tag in ("L", "R"):
        sk[f"upper_arm.{tag}"] = (joints[f"shoulder.{tag}"], joints[f"elbow.{tag}"])
        sk[f"forearm.{tag}"] = (joints[f"elbow.{tag}"], joints[f"wrist.{tag}"])
        sk[f"hand.{tag}"] = (joints[f"wrist.{tag}"], joints[f"hand_tip.{tag}"])
        sk[f"thigh.{tag}"] = (joints[f"hip.{tag}"], joints[f"knee.{tag}"])
        sk[f"shin.{tag}"] = (joints[f"knee.{tag}"], joints[f"ankle.{tag}"])
        sk[f"foot.{tag}"] = (joints[f"ankle.{tag}"], ct.lerp(joints[f"ankle.{tag}"], joints[f"toe.{tag}"], 0.8))
    return sk


def run_template(job: dict[str, Any]) -> dict[str, Any]:
    sem = ct.Semantic.from_dict(job["semantic"])
    if sem.pose != "T":
        raise ValueError(f"semantic.yaml pose {sem.pose!r}: only T-pose references are supported for now")
    out = Path(job["template_dir"])
    out.mkdir(parents=True, exist_ok=True)
    objs = mesh_objects()
    if not objs:
        raise ValueError("normalized.blend has no mesh")
    verts0, faces0 = combined_mesh(objs)
    bm = bmesh.new()
    vmap = [bm.verts.new(v) for v in verts0]
    for f in faces0:
        try:
            bm.faces.new([vmap[i] for i in f])
        except ValueError:
            pass
    bm.verts.index_update()
    repair = _repair(bm)
    loops = _support_loops(bm, sem)
    bm.verts.index_update()
    verts = [tuple(v.co) for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()

    weights, regions, chains = ct.classify(verts, sem)
    regions = ct.apply_overrides(ct.face_regions(verts, regions, sem), sem)
    u = [round(ct.chain_u(v, c, sem), 4) for v, c in zip(verts, chains)]
    lm = ct.find_landmarks(verts, chains, regions, sem)
    points = ct.evaluate(lm, verts)
    dy = -(points["ankle.L"][1] + points["ankle.R"][1]) / 2          # ankles on y = 0, like the rig
    verts = [(x, y + dy, z) for x, y, z in verts]
    points = ct.evaluate(lm, verts)
    verts_a = ct.to_apose(verts, weights, chains, points)
    joints = ct.template_joints(ct.evaluate(lm, verts_a))
    rounded = [[round(c, 5) for c in v] for v in verts_a]
    verts_a = [tuple(v) for v in rounded]

    # -- the production template: one mesh, humanoid_v1 groups + region_* groups, a fitted rig
    keep_only([])
    mesh = bpy.data.meshes.new(f"{job['template_id']}_mesh")
    mesh.from_pydata(verts_a, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(job["template_id"], mesh)
    bpy.context.scene.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = False
    groups: dict[str, bpy.types.VertexGroup] = {}
    for i, w in enumerate(weights):
        for bone, value in w.items():
            g = groups.get(bone) or obj.vertex_groups.new(name=bone)
            groups[bone] = g
            g.add([i], value, "REPLACE")
    for i, r in enumerate(regions):
        name = "region_" + r.replace(".", "_")
        g = groups.get(name) or obj.vertex_groups.new(name=name)
        groups[name] = g
        g.add([i], 1.0, "REPLACE")
    tpl_stub = ct.Template(job["template_id"], job.get("kind", "body"), verts_a, faces, weights, regions, lm,
                           joints, {})
    b0 = ct.template_body(tpl_stub)
    rig = build_rig("template_rig", template_skeleton(joints, b0))
    obj.parent = rig
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    for name, p in joints.items():
        e = bpy.data.objects.new(f"lm_{name}", None)
        e.empty_display_type = "SPHERE"
        e.empty_display_size = 0.012
        e.location = p
        e.parent = rig
        bpy.context.scene.collection.objects.link(e)
    obj["template_id"] = job["template_id"]
    obj["template_kind"] = job.get("kind", "body")
    obj["source_reference"] = job["reference_id"]
    bpy.context.scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "template.blend"), copy=True, compress=True)
    log(f"saved {out / 'template.blend'}")

    tris = sum(len(f) - 2 for f in faces)
    data = {
        "format": ct.FORMAT, "id": job["template_id"], "kind": job.get("kind", "body"),
        "title": job.get("title", ""), "pose": "A", "a_pose_deg": round(math.degrees(hu.A_POSE), 2),
        "height": round(joints["head_top"][2], 5), "units": "m", "axes": "Blender: Z up, front −Y, left +X",
        "rig": hu.RIG,
        "source": {**job["provenance"], "semantic": job["semantic"]},
        "extraction": {"repair": repair, "support_loops": loops, "ankle_shift_y": round(dy, 5),
                       "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "blender": bpy.app.version_string},
        "stats": {"vertices": len(verts_a), "faces": len(faces), "triangles": tris,
                  "regions": dict(sorted(Counter(regions).items())),
                  "max_influences": max(len(w) for w in weights)},
        "body": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in b0.__dict__.items()},
        "joints": {k: [round(c, 5) for c in v] for k, v in joints.items()},
        "landmarks": {k: {str(i): round(c, 6) for i, c in v.items()} for k, v in lm.items()},
        "mesh": {"verts": rounded, "faces": faces},
        "weights": [{b: round(w, 4) for b, w in wt.items()} for wt in weights],
        "regions": regions,
        "chains": chains,
        "u": u,
    }
    (out / "template.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    color_by_regions(obj, regions)
    export_glb(out / "template.glb", [obj], colors=True)
    for e in [o for o in bpy.data.objects if o.name.startswith("lm_")]:
        e.hide_render = True
    files = preview.render(out, 640, *STANDARD_FRAME, [], views={"preview": preview.CHARACTER_VIEWS["34"]},
                           prefix="")
    _clear_preview_rig()
    ref_prev = Path(job["ref_dir"]) / "studies" / "body"
    files.update({f"template_{k}": v for k, v in render_previews(ref_prev, [obj], prefix=f"{job['template_id']}_",
                                                                 views=("front", "34", "side")).items()})
    return {"template": {"dir": str(out), "stats": data["stats"], "repair": repair, "support_loops": loops,
                         "previews": files}}


def main() -> int:
    args = parse_args()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    started = time.monotonic()
    report: dict[str, Any] = {"status": "failed", "error": None, "mode": args.mode,
                              "blender_version": bpy.app.version_string}
    code = 0
    try:
        report.update(run_build(job) if args.mode == "build" else run_template(job))
        report["status"] = "ok"
    except Exception as exc:
        traceback.print_exc()
        report["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    report["duration_s"] = round(time.monotonic() - started, 2)
    Path(job["report"]).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"{args.mode}: {report['status']} in {report['duration_s']}s")
    return code


if __name__ == "__main__":
    sys.exit(main())
