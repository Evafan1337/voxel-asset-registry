"""Sidebar panel for editing a manual variant in the Blender GUI (started by backend/manual.py).

    blender <variants/v004.blend> --python builder/blender_session.py -- \
        --ref components/lh_hall@v004 --server http://127.0.0.1:8000 --palette '{"steel": "#..."}' \
        --sockets a,b --grid 28,27,24 --voxel-size 0.25 --pivot bottom_center

View3D → sidebar (N) → Registry:
- asset scenes: every slot is its own object tree, parented to the slot it stands on;
  "Выделить деталь целиком" picks the slot object of the clicked mesh;
- snapping starts on: voxel-grid increments plus vertex docking (closest point);
- palette: paints selected faces (Edit Mode) or whole selected meshes (Object Mode) with a
  palette color, the "Color" attribute and the shared material the builder expects;
- sockets and envelope: live status of the checks the build will run;
- "Сохранить и собрать": saves the file and asks the registry server to rebuild the variant.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import bpy
from bpy.app.handlers import persistent
from mathutils import Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import voxlib  # noqa: E402


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="builder/blender_session.py")
    parser.add_argument("--ref", required=True)            # components/<id>@<vid>
    parser.add_argument("--server", required=True)
    parser.add_argument("--palette", required=True)        # JSON {name: "#rrggbb"}
    parser.add_argument("--sockets", default="")
    parser.add_argument("--grid", default="0,0,0")
    parser.add_argument("--voxel-size", type=float, default=0.25)
    parser.add_argument("--pivot", default="bottom_center")  # ground: geometry may hover above 0
    return parser.parse_args(argv)


ARGS = parse_args()
PALETTE: dict[str, str] = json.loads(ARGS.palette)
SOCKETS = [s for s in ARGS.sockets.split(",") if s]
ENVELOPE = [int(v) * ARGS.voxel_size for v in ARGS.grid.split(",")]   # glTF order: X, Y up, Z
KIND, _, _TARGET = ARGS.ref.partition("/")
ENTITY_ID, _, VID = _TARGET.partition("@")
EXPECTED_FILE = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
TOLERANCE = 0.02

voxlib.configure(PALETTE, ARGS.voxel_size, 3)


# ---------------------------------------------------------------------- painting

def _color_attribute(mesh: bpy.types.Mesh, fill: tuple[float, float, float, float]) -> bpy.types.Attribute:
    """The builder's color layout: byte colors per face corner, named "Color"."""
    attr = mesh.color_attributes.get("Color")
    if attr is not None and (attr.domain != "CORNER" or attr.data_type != "BYTE_COLOR"):
        mesh.color_attributes.remove(attr)
        attr = None
    if attr is None:
        attr = mesh.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
        attr.data.foreach_set("color_srgb", list(fill) * len(mesh.loops))
    mesh.color_attributes.active_color = attr
    mesh.color_attributes.render_color_index = mesh.color_attributes.find("Color")
    return attr


def paint(mesh: bpy.types.Mesh, color: str, *, selected_only: bool) -> int:
    rgba = voxlib.hex_to_srgb(PALETTE[color])
    attr = _color_attribute(mesh, rgba)
    flat = [0.0] * (len(mesh.loops) * 4)
    attr.data.foreach_get("color_srgb", flat)
    painted = 0
    for poly in mesh.polygons:
        if selected_only and not poly.select:
            continue
        painted += 1
        for li in poly.loop_indices:
            flat[li * 4:li * 4 + 4] = rgba
    attr.data.foreach_set("color_srgb", flat)
    voxlib.CTX.material = None
    material = voxlib.palette_material()
    if list(mesh.materials) != [material]:
        mesh.materials.clear()
        mesh.materials.append(material)
        for poly in mesh.polygons:
            poly.material_index = 0
    mesh.update()
    return painted


class REGISTRY_OT_paint(bpy.types.Operator):
    """Покрасить выделенные грани (Edit Mode) или выделенные объекты целиком цветом палитры"""

    bl_idname = "registry.paint"
    bl_label = "Покрасить"
    bl_options = {"REGISTER", "UNDO"}

    color: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return any(o.type == "MESH" for o in context.selected_objects) or context.mode == "EDIT_MESH"

    def execute(self, context: bpy.types.Context) -> set[str]:
        if self.color not in PALETTE:
            self.report({"ERROR"}, f"нет цвета {self.color} в palette.yaml")
            return {"CANCELLED"}
        edit = context.mode == "EDIT_MESH"
        targets = list(context.objects_in_mode) if edit else [o for o in context.selected_objects if o.type == "MESH"]
        if edit:
            bpy.ops.object.mode_set(mode="OBJECT")   # flush edit data so the selection is readable
        try:
            faces = sum(paint(mesh, self.color, selected_only=edit) for mesh in {o.data for o in targets})
        finally:
            if edit:
                bpy.ops.object.mode_set(mode="EDIT")
        self.report({"INFO"}, f"{self.color}: {faces} гр.")
        return {"FINISHED"}


# ---------------------------------------------------------------------- save & build

class REGISTRY_OT_save_build(bpy.types.Operator):
    """Сохранить .blend и пересобрать вариант в реестре (результат — в браузере)"""

    bl_idname = "registry.save_build"
    bl_label = "Сохранить и собрать"

    def execute(self, context: bpy.types.Context) -> set[str]:
        current = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
        if EXPECTED_FILE is None or current != EXPECTED_FILE:
            self.report({"ERROR"}, f"открыт другой файл; реестр собирает {EXPECTED_FILE}")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")   # edit-mode changes are not in the saved mesh
        bpy.ops.wm.save_mainfile()
        url = f"{ARGS.server}/api/{KIND}/{ENTITY_ID}/variants/{VID}/rebuild"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=10) as resp:
                result = json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.report({"ERROR"}, f"файл сохранён, но сервер реестра недоступен: {exc}")
            return {"CANCELLED"}
        if result.get("state") == "invalid":
            self.report({"ERROR"}, f"рецепт невалиден: {result.get('error')}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"сохранено; сборка {VID}: {result.get('state')} ({result.get('hash')})")
        return {"FINISHED"}


# ---------------------------------------------------------------------- asset parts

def _part_root(obj: bpy.types.Object | None) -> bpy.types.Object | None:
    """The slot object a mesh belongs to in an asset scene (a table for its leg)."""
    while obj is not None and not obj.get("registry_slot"):
        obj = obj.parent
    return obj


def _part_objects(root: bpy.types.Object) -> list[bpy.types.Object]:
    """The slot object and its own meshes, without the parts mounted on it (a roof on a hall)."""
    found, stack = [root], list(root.children)
    while stack:
        obj = stack.pop()
        if not obj.get("registry_slot"):
            found.append(obj)
            stack.extend(obj.children)
    return found


class REGISTRY_OT_select_part(bpy.types.Operator):
    """Выделить деталь целиком (для дубля и удаления); то, что стоит на ней, всё равно едет вместе с ней"""

    bl_idname = "registry.select_part"
    bl_label = "Выделить деталь целиком"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.mode == "OBJECT" and _part_root(context.active_object) is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        active = _part_root(context.active_object)
        roots = {r for r in (_part_root(o) for o in context.selected_objects) if r is not None} | {active}
        bpy.ops.object.select_all(action="DESELECT")
        for root in roots:
            for obj in _part_objects(root):
                obj.select_set(True)
        context.view_layer.objects.active = active
        return {"FINISHED"}


# ---------------------------------------------------------------------- panel

class RegistryColor(bpy.types.PropertyGroup):
    swatch: bpy.props.FloatVectorProperty(subtype="COLOR_GAMMA", size=3, min=0.0, max=1.0)


def _fill_swatches() -> None:
    wm = bpy.context.window_manager
    wm.registry_palette.clear()
    for name, value in PALETTE.items():
        item = wm.registry_palette.add()
        item.name = name
        item.swatch = voxlib.hex_to_srgb(value)[:3]


def _scene_status(scene: bpy.types.Scene) -> tuple[list[str], list[float] | None, float]:
    """Missing sockets, mesh bbox size in glTF order and the lowest point (Blender Z)."""
    present = {re.sub(r"\.\d{3}$", "", o.name)[len("socket_"):] for o in scene.objects
               if o.type == "EMPTY" and o.name.startswith("socket_")}
    lo = Vector((float("inf"),) * 3)
    hi = Vector((float("-inf"),) * 3)
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            co = obj.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, co))
            hi = Vector(map(max, hi, co))
    if lo.x == float("inf"):
        return [s for s in SOCKETS if s not in present], None, 0.0
    size = hi - lo
    return [s for s in SOCKETS if s not in present], [size.x, size.z, size.y], lo.z


class VIEW3D_PT_registry(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Registry"
    bl_label = "Voxel Asset Registry"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text=f"{ENTITY_ID} @ {VID}", icon="MESH_CUBE")
        layout.operator(REGISTRY_OT_save_build.bl_idname, icon="FILE_REFRESH")

        part = _part_root(context.active_object)
        if KIND == "assets":
            box = layout.box()
            box.label(text=f"Деталь: {part.name}" if part else "Деталь: —", icon="OUTLINER_OB_GROUP_INSTANCE")
            if part is not None and part.get("registry_ref"):
                box.label(text=f"из {part['registry_ref']}")
            box.operator(REGISTRY_OT_select_part.bl_idname, icon="RESTRICT_SELECT_OFF")
            snap = context.scene.tool_settings
            box.prop(snap, "use_snap", text=f"Привязка: шаг {ARGS.voxel_size:g} м + вершины")

        missing, size, bottom = _scene_status(context.scene)
        box = layout.box()
        box.label(text=f"Сокеты: {len(SOCKETS) - len(missing)}/{len(SOCKETS)}",
                  icon="ERROR" if missing else "CHECKMARK")
        for name in missing:
            row = box.row()
            row.alert = True
            row.label(text=f"нет socket_{name}")
        if size is None:
            box.label(text="нет мешей", icon="ERROR")
        else:
            for axis, value, limit in zip(("X", "высота", "глубина"), size, ENVELOPE):
                row = box.row()
                row.alert = value > limit + TOLERANCE
                row.label(text=f"{axis}: {value:.2f} / {limit:.2f} м")
            row = box.row()
            if ARGS.pivot == "ground":
                row.alert = bottom < -TOLERANCE
                row.label(text=f"низ: {bottom:.3f} м (не ниже 0)")
            else:
                row.alert = abs(bottom) > TOLERANCE
                row.label(text=f"низ: {bottom:.3f} м (должен быть 0)")
        box.label(text="socket_* не удалять", icon="INFO")

        box = layout.box()
        box.label(text="Палитра" + (" → выделенные грани" if context.mode == "EDIT_MESH" else " → выделенные объекты"))
        grid = box.grid_flow(columns=2, even_columns=True, align=True)
        for item in context.window_manager.registry_palette:
            split = grid.split(factor=0.25, align=True)
            split.prop(item, "swatch", text="")
            split.operator(REGISTRY_OT_paint.bl_idname, text=item.name).color = item.name


# ---------------------------------------------------------------------- startup

def _setup_views() -> None:
    """Vertex colors in Solid mode and the sidebar open on the Registry tab."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.color_type = "VERTEX"
                    space.show_region_ui = True
                    space.overlay.grid_scale = ARGS.voxel_size   # increment snapping step


def _setup_snapping() -> None:
    """Moves land on the voxel grid; near another part's corner they dock to its vertex."""
    snap = bpy.context.scene.tool_settings
    snap.use_snap = True
    snap.snap_elements_base = {"INCREMENT", "VERTEX"}
    snap.use_snap_grid_absolute = True
    snap.snap_target = "CLOSEST"


def _startup() -> None:
    _fill_swatches()
    _setup_views()
    _setup_snapping()


@persistent
def _on_load(_dummy: object) -> None:
    bpy.app.timers.register(_startup, first_interval=0.1)


CLASSES = (RegistryColor, REGISTRY_OT_paint, REGISTRY_OT_save_build, REGISTRY_OT_select_part,
           VIEW3D_PT_registry)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.registry_palette = bpy.props.CollectionProperty(type=RegistryColor)
    bpy.app.handlers.load_post.append(_on_load)
    bpy.app.timers.register(_startup, first_interval=0.1)


register()
