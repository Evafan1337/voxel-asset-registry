"""Geometry helpers for registry generators (runs inside Blender).

Conventions:
- Blender space: Z up, meters. The exporter converts to glTF +Y up.
- Pivot is bottom_center: generators build around (0, 0, 0) with the model standing on z = 0.
- Geometry is written with explicit coordinates through bmesh. Objects stay at identity
  transforms unless they are meant to move (rotors, sockets) — no transform_apply tricks.
- Every face carries a palette color (vertex color attribute "Color", sRGB bytes).
- Animation (level 3) is a seamless loop of LOOP_FRAMES at FPS: every animated channel must
  return to an equivalent state at the end of the loop. The builder merges all actions of an
  asset into ONE glTF animation named "work".
- Sockets: an empty named socket_<name>. A component mounted on it is placed with its pivot at
  the socket origin and its local axes = socket axes (component "up" = socket +Z).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

try:  # package import in tests / top-level import in headless Blender
    from . import semantic as _semantic
except ImportError:
    import semantic as _semantic

Vec = Sequence[float]
Bounds = _semantic.Bounds
evenly_spaced = _semantic.evenly_spaced
centered_array = _semantic.centered_array
mirrored_pair = _semantic.mirrored_pair
distribute_between = _semantic.distribute_between
support_segment = _semantic.support_segment


def quantize(value: float, *, grid: str | float = "structural") -> float:
    """Snap explicitly to structural (voxel) or detail (quarter-voxel) grid."""
    return _semantic.quantize(value, grid=grid, voxel_size=CTX.voxel_size)


def snap_point(point: Vec, *, grid: str | float = "structural") -> tuple[float, float, float]:
    """Snap a 3D anchor explicitly; no geometry is automatically quantized."""
    return _semantic.snap_point(point, grid=grid, voxel_size=CTX.voxel_size)

# Face corner tables for a unit cube: (normal, 4 corners CCW seen from outside).
_FACES: dict[str, tuple[tuple[int, int, int], tuple[tuple[int, int, int], ...]]] = {
    "+x": ((1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
    "-x": ((-1, 0, 0), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
    "+y": ((0, 1, 0), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
    "-y": ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
    "+z": ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    "-z": ((0, 0, -1), ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0))),
}
FACE_KEYS = tuple(_FACES)

FPS = 24
LOOP_FRAMES = 96  # 4 seconds; the one shared loop length for all "work" animations


class _Context:
    palette: dict[str, tuple[float, float, float, float]] = {}
    voxel_size: float = 0.25
    level: int = 1
    material: bpy.types.Material | None = None
    surfaces: dict[str, str] = {}                          # color → material class (palette.yaml)
    surface_types: dict[str, dict[str, float]] = {}


CTX = _Context()


def configure(palette_hex: dict[str, str], voxel_size: float, level: int) -> None:
    CTX.palette = {name: hex_to_srgb(value) for name, value in palette_hex.items()}
    CTX.voxel_size = voxel_size
    CTX.level = level
    CTX.material = None


def configure_surfaces(palette: dict) -> None:
    """Material classes of colors (`surfaces`, `surface_types` of palette.yaml); the rest is paint."""
    CTX.surfaces = dict(palette.get("surfaces") or {})
    CTX.surface_types = {k: dict(v) for k, v in (palette.get("surface_types") or {}).items()}


def surface_of(color: str) -> str:
    return CTX.surfaces.get(color, "paint")


def voxel_size() -> float:
    return CTX.voxel_size


def level() -> int:
    """Complexity level of the variant being built: 0 blockout, 1 silhouette, 2 details, 3 animation."""
    return CTX.level


def hex_to_srgb(value: str) -> tuple[float, float, float, float]:
    value = value.lstrip("#")
    return (int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255, 1.0)


def palette_names() -> list[str]:
    return list(CTX.palette)


def _check_color(name: str) -> str:
    if name not in CTX.palette:
        raise KeyError(f"color '{name}' is not in registry/palette.yaml ({', '.join(CTX.palette)})")
    return name


def palette_material(surface: str = "paint") -> bpy.types.Material:
    """One shared material per surface class: Principled BSDF fed by the vertex color attribute.
    Paint is `voxel_palette`, the material of every model before surface classes; other classes
    (`voxel_metal`, `voxel_light`…) take metallic / roughness / emission from palette.yaml, the
    emission colored by the vertex color."""
    if surface != "paint":
        return _surface_material(surface)
    if CTX.material is not None:
        return CTX.material
    mat = bpy.data.materials.get("voxel_palette") or bpy.data.materials.new("voxel_palette")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Color"
    bsdf.inputs["Roughness"].default_value = 0.85
    mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    CTX.material = mat
    return mat


def _surface_material(surface: str) -> bpy.types.Material:
    props = CTX.surface_types[surface]
    name = f"voxel_{surface}"
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Color"
    bsdf.inputs["Metallic"].default_value = props.get("metallic", 0.0)
    bsdf.inputs["Roughness"].default_value = props.get("roughness", 0.85)
    links = mat.node_tree.links
    links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    texture = props.get("texture")
    if texture and texture["style"] != "none":
        _metal_texture_nodes(mat, bsdf, attr, texture, props)
    if props.get("emission", 0.0) > 0.0:
        links.new(attr.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = props["emission"]
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    mat["surface"] = surface
    return mat


def _metal_texture_nodes(mat, bsdf, attr, config, props):
    import json
    import hashlib
    try:
        from .metal_texture import SIZE, pixels
    except ImportError:
        from metal_texture import SIZE, pixels
    key = hashlib.sha256(json.dumps([config, props.get("roughness", .25), props.get("metallic", .65)], sort_keys=True).encode()).hexdigest()[:16]
    albedo, orm = pixels(config, props.get("roughness", .25), props.get("metallic", .65))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    textures = []
    for suffix, data in (("albedo", albedo), ("orm", orm)):
        name = f"pixel_metal_{key}_{suffix}"
        image = bpy.data.images.get(name)
        if image is None:
            image = bpy.data.images.new(name, width=SIZE, height=SIZE, alpha=True)
            image.colorspace_settings.name = "sRGB" if suffix == "albedo" else "Non-Color"
            image.pixels.foreach_set(data)
            image.pack()
        node = nodes.new("ShaderNodeTexImage")
        node.image, node.interpolation, node.extension = image, "Closest", "REPEAT"
        textures.append(node)
    mix = nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1
    links.new(attr.outputs["Color"], mix.inputs[1])
    links.new(textures[0].outputs["Color"], mix.inputs[2])
    links.new(mix.outputs[0], bsdf.inputs["Base Color"])
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.mode = "RGB"
    links.new(textures[1].outputs["Color"], separate.inputs[0])
    links.new(separate.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(separate.outputs["Blue"], bsdf.inputs["Metallic"])
    mat["metal_texture"] = config["style"]


def palette_emission(obj: bpy.types.Object, color: str) -> None:
    """Opt-in uniform lamp color. glTF vertex colors affect albedo, not emission.

    Use on single-color emitters so their Blender color survives in Godot/Three.
    Clone the shared surface material; other lamps keep their own appearance.
    """
    rgba = CTX.palette[_check_color(color)]
    linear = tuple(value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
                   for value in rgba[:3]) + (1.,)
    for slot in obj.material_slots:
        source = slot.material
        if source is None:
            continue
        name = f"{source.name}_emission_{color}"
        material = bpy.data.materials.get(name)
        if material is None:
            material = source.copy()
            material.name = name
            material["emission_color"] = color
            for node in material.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    socket = node.inputs["Emission Color"]
                    for link in list(socket.links):
                        material.node_tree.links.remove(link)
                    socket.default_value = linear
        slot.material = material


def link(obj: bpy.types.Object, parent: bpy.types.Object | None = None) -> bpy.types.Object:
    if obj.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
        obj.matrix_parent_inverse = Matrix.Identity(4)
    return obj


class MeshBuilder:
    """Collects colored quads/polygons and turns them into one flat-shaded mesh object."""

    def __init__(self) -> None:
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[tuple[list[int], str]] = []

    def polygon(self, points: Iterable[Vec], color: str) -> None:
        _check_color(color)
        start = len(self.verts)
        pts = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
        self.verts.extend(pts)
        self.faces.append((list(range(start, start + len(pts))), color))

    def box(self, mn: Vec, mx: Vec, color: str | Callable[[str], str], *, skip: Iterable[str] = ()) -> None:
        """Axis-aligned box from min to max corner (meters). `color` may be a function of face key."""
        skipped = set(skip)
        for key, (_normal, corners) in _FACES.items():
            if key in skipped:
                continue
            pts = [(mx[0] if c[0] else mn[0], mx[1] if c[1] else mn[1], mx[2] if c[2] else mn[2]) for c in corners]
            self.polygon(pts, color(key) if callable(color) else color)

    def platform(self, bounds: Bounds, color: str) -> None:
        """Deck/slab occupying named bounds. Pair with support_to_ground for legs."""
        self.box(bounds.minimum, bounds.maximum, color)

    def beam_between(self, start: Vec, end: Vec, width: float, color: str,
                     *, depth: float | None = None) -> None:
        """Rectangular beam whose end planes are centred exactly on both anchors."""
        corners = _semantic.beam_corners(start, end, width, depth=depth)
        for face in ((0, 3, 2, 1), (4, 5, 6, 7),
                     (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.polygon((corners[i] for i in face), color)

    def support_to_ground(self, top: Vec, width: float, color: str, *,
                          ground_z: float = 0.0, depth: float | None = None) -> None:
        """Vertical support touching ground_z and the underside at top exactly."""
        start, end = _semantic.support_segment(top, ground_z=ground_z)
        self.beam_between(start, end, width, color, depth=depth)

    def frame(self, bounds: Bounds, thickness: float, color: str, *,
              side: str = "front", bottom: bool = False) -> None:
        """Four-sided or open-bottom rectangular wall frame contained in bounds."""
        t = float(thickness)
        if not math.isfinite(t) or t <= 0:
            raise ValueError("frame thickness must be positive and finite")
        if side in ("front", "back"):
            if t * 2 >= bounds.size[0] or t >= bounds.size[1] or t * 2 >= bounds.size[2]:
                raise ValueError("frame thickness exceeds bounds")
            y0, y1 = ((bounds.front, bounds.front + t) if side == "front"
                      else (bounds.back - t, bounds.back))
            self.box((bounds.left, y0, bounds.bottom), (bounds.left + t, y1, bounds.top), color)
            self.box((bounds.right - t, y0, bounds.bottom), (bounds.right, y1, bounds.top), color)
            self.box((bounds.left + t, y0, bounds.top - t), (bounds.right - t, y1, bounds.top), color)
            if bottom:
                self.box((bounds.left + t, y0, bounds.bottom),
                         (bounds.right - t, y1, bounds.bottom + t), color)
        elif side in ("left", "right"):
            if t >= bounds.size[0] or t * 2 >= bounds.size[1] or t * 2 >= bounds.size[2]:
                raise ValueError("frame thickness exceeds bounds")
            x0, x1 = ((bounds.left, bounds.left + t) if side == "left"
                      else (bounds.right - t, bounds.right))
            self.box((x0, bounds.front, bounds.bottom), (x1, bounds.front + t, bounds.top), color)
            self.box((x0, bounds.back - t, bounds.bottom), (x1, bounds.back, bounds.top), color)
            self.box((x0, bounds.front + t, bounds.top - t), (x1, bounds.back - t, bounds.top), color)
            if bottom:
                self.box((x0, bounds.front + t, bounds.bottom),
                         (x1, bounds.back - t, bounds.bottom + t), color)
        else:
            raise ValueError(f"unknown frame side: {side}")

    def railing(self, start: Vec, end: Vec, *, height: float, post_count: int,
                width: float, color: str) -> tuple[tuple[float, float, float], ...]:
        """Even posts from a deck edge to one continuous top rail; returns post anchors."""
        if not math.isfinite(height) or height <= 0:
            raise ValueError("railing height must be positive and finite")
        if post_count < 2:
            raise ValueError("railing needs at least two posts")
        anchors = _semantic.distribute_between(start, end, post_count)
        if any(abs(a[2] - anchors[0][2]) > 1e-8 for a in anchors):
            raise ValueError("railing edge must be horizontal")
        for p in anchors:
            self.beam_between(p, (p[0], p[1], p[2] + height), width, color)
        a, b = anchors[0], anchors[-1]
        self.beam_between((a[0], a[1], a[2] + height),
                          (b[0], b[1], b[2] + height), width, color)
        return anchors

    def box_transformed(self, size: Vec, color: str, matrix: Matrix) -> None:
        """Box of `size` centered at the origin, transformed by a 4x4 matrix (for rotated parts)."""
        half = Vector(size) / 2
        for _key, (_normal, corners) in _FACES.items():
            pts = []
            for c in corners:
                local = Vector((half.x if c[0] else -half.x, half.y if c[1] else -half.y, half.z if c[2] else -half.z))
                pts.append(tuple(matrix @ local))
            self.polygon(pts, color)

    @staticmethod
    def _orient(axis: str) -> Callable[[tuple[float, float, float]], tuple[float, float, float]]:
        """Cyclic axis permutation (keeps winding): a Z-aligned shape becomes X- or Y-aligned."""
        if axis == "X":
            return lambda p: (p[2], p[0], p[1])
        if axis == "Y":
            return lambda p: (p[1], p[2], p[0])
        return lambda p: p

    def prism(self, radius: float, z0: float, z1: float, color: str, *, sides: int = 12,
              phase: float = 0.0, center: Vec = (0.0, 0.0), axis: str = "Z") -> None:
        """Regular n-gon prism (cylinder stand-in) along `axis`; z0/z1 are coordinates on that axis,
        `center` the position in the other two axes (for axis X: (y, z); for Y: (z, x))."""
        o = self._orient(axis)
        pts = [(center[0] + radius * math.cos(phase + 2 * math.pi * i / sides),
                center[1] + radius * math.sin(phase + 2 * math.pi * i / sides)) for i in range(sides)]
        for i in range(sides):
            (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % sides]
            self.polygon([o((xa, ya, z0)), o((xb, yb, z0)), o((xb, yb, z1)), o((xa, ya, z1))], color)
        self.polygon([o((x, y, z1)) for x, y in pts], color)
        self.polygon([o((x, y, z0)) for x, y in reversed(pts)], color)

    def ring(self, r_in: float, r_out: float, z0: float, z1: float, color: str, *, sides: int = 16,
             phase: float = 0.0, axis: str = "Z") -> None:
        """Flat annulus along `axis` (gear rims, flanges, pipe collars)."""
        o = self._orient(axis)
        ang = [phase + 2 * math.pi * i / sides for i in range(sides)]
        outer = [(r_out * math.cos(a), r_out * math.sin(a)) for a in ang]
        inner = [(r_in * math.cos(a), r_in * math.sin(a)) for a in ang]
        for i in range(sides):
            j = (i + 1) % sides
            (oa, ob), (ia, ib) = (outer[i], outer[j]), (inner[i], inner[j])
            self.polygon([o((oa[0], oa[1], z0)), o((ob[0], ob[1], z0)), o((ob[0], ob[1], z1)), o((oa[0], oa[1], z1))], color)
            self.polygon([o((ib[0], ib[1], z0)), o((ia[0], ia[1], z0)), o((ia[0], ia[1], z1)), o((ib[0], ib[1], z1))], color)
            self.polygon([o((oa[0], oa[1], z1)), o((ob[0], ob[1], z1)), o((ib[0], ib[1], z1)), o((ia[0], ia[1], z1))], color)
            self.polygon([o((ia[0], ia[1], z0)), o((ib[0], ib[1], z0)), o((ob[0], ob[1], z0)), o((oa[0], oa[1], z0))], color)

    def chamfer_box(self, mn: Vec, mx: Vec, color: str, *, chamfer: float = 0.0, taper: float = 0.0) -> None:
        """Box with chamfered vertical edges (octagonal footprint) — a cheap bevel look for chunky
        blockouts. taper (0..0.9) shrinks the top outline toward the center."""
        x0, y0, x1, y1 = mn[0], mn[1], mx[0], mx[1]
        c = max(0.0, min(chamfer, (x1 - x0) / 2 - 1e-4, (y1 - y0) / 2 - 1e-4))
        if c > 1e-4:
            outline = [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
                       (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]
        else:
            outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        cx, cy, k = (x0 + x1) / 2, (y0 + y1) / 2, 1.0 - min(max(taper, 0.0), 0.9)
        top = [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in outline]
        z0, z1 = mn[2], mx[2]
        n = len(outline)
        for i in range(n):
            (ax, ay), (bx, by) = outline[i], outline[(i + 1) % n]
            (tax, tay), (tbx, tby) = top[i], top[(i + 1) % n]
            self.polygon([(ax, ay, z0), (bx, by, z0), (tbx, tby, z1), (tax, tay, z1)], color)
        self.polygon([(x, y, z1) for x, y in top], color)
        self.polygon([(x, y, z0) for x, y in reversed(outline)], color)

    def sphere(self, center: Vec, radius: float, color: str, *, rings: int = 5, sides: int = 10,
               squash: float = 1.0) -> None:
        """Low-poly faceted sphere (flat shading makes the facets read as chunky armor).
        squash < 1 flattens it vertically."""
        cx, cy, cz = center
        pts = []
        for k in range(rings + 1):
            phi = -math.pi / 2 + math.pi * k / rings
            ring = [(cx + radius * math.cos(phi) * math.cos(2 * math.pi * j / sides),
                     cy + radius * math.cos(phi) * math.sin(2 * math.pi * j / sides),
                     cz + radius * squash * math.sin(phi)) for j in range(sides)]
            pts.append(ring)
        for k in range(rings):
            for j in range(sides):
                a, b = pts[k][j], pts[k][(j + 1) % sides]
                c, d = pts[k + 1][(j + 1) % sides], pts[k + 1][j]
                if k == 0:
                    self.polygon([a, c, d], color)            # bottom pole: a == b
                elif k == rings - 1:
                    self.polygon([a, b, c], color)            # top pole: c == d
                else:
                    self.polygon([a, b, c, d], color)

    def strut(self, p0: Vec, p1: Vec, width: float, color: str, *, depth: float | None = None) -> None:
        """Square beam from point p0 to p1 (legs, braces, rods)."""
        a, b = Vector(p0), Vector(p1)
        direction = b - a
        length = direction.length
        if length < 1e-6:
            return
        rot = direction.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
        matrix = Matrix.Translation((a + b) / 2) @ rot
        self.box_transformed((width, depth if depth is not None else width, length), color, matrix)

    def extend(self, other: MeshBuilder) -> None:
        offset = len(self.verts)
        self.verts.extend(other.verts)
        self.faces.extend(([i + offset for i in idx], color) for idx, color in other.faces)

    def to_object(self, name: str, parent: bpy.types.Object | None = None,
                  location: Vec = (0.0, 0.0, 0.0), *,
                  semantic_part: str | None = None) -> bpy.types.Object:
        palette = list(CTX.palette)
        bm = bmesh.new()
        color_layer = bm.faces.layers.int.new("palette_index")
        bverts = [bm.verts.new(co) for co in self.verts]
        for indices, color in self.faces:
            face = bm.faces.new([bverts[i] for i in indices])
            face.smooth = False
            face[color_layer] = palette.index(color)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()

        indices_attr = mesh.attributes["palette_index"]
        face_colors = [0] * len(mesh.polygons)
        indices_attr.data.foreach_get("value", face_colors)
        loop_colors: list[float] = [0.0] * (len(mesh.loops) * 4)
        for poly in mesh.polygons:
            rgba = CTX.palette[palette[face_colors[poly.index]]]
            for li in poly.loop_indices:
                loop_colors[li * 4:li * 4 + 4] = rgba
        mesh.attributes.remove(mesh.attributes["palette_index"])
        col = mesh.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
        col.data.foreach_set("color_srgb", loop_colors)
        mesh.color_attributes.active_color = col
        mesh.color_attributes.render_color_index = 0
        surfaces = [surface_of(palette[i]) for i in face_colors]
        classes = sorted(set(surfaces), key=lambda c: (c != "paint", c)) or ["paint"]   # paint: slot 0
        for surface in classes:
            mesh.materials.append(palette_material(surface))
        if len(classes) > 1:
            slot = {c: i for i, c in enumerate(classes)}
            mesh.polygons.foreach_set("material_index", [slot[c] for c in surfaces])
        mesh.update()

        if any(CTX.surface_types.get(surface, {}).get("texture") for surface in classes):
            # Dominant-axis planar UVs preserve pixel density on arbitrary blockout faces.
            layer = mesh.uv_layers.new(name="UVMap")
            for poly in mesh.polygons:
                axis = max(range(3), key=lambda i: abs(poly.normal[i]))
                plane = [i for i in range(3) if i != axis]
                props = CTX.surface_types.get(classes[poly.material_index], {})
                density = props.get("texture", {}).get("density", 32.0) / 64.0
                for loop_index in poly.loop_indices:
                    point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                    layer.data[loop_index].uv = (point[plane[0]] * density, point[plane[1]] * density)

        obj = bpy.data.objects.new(name, mesh)
        obj.location = location
        if semantic_part is not None:
            mark_part(obj, semantic_part)
        return link(obj, parent)


class VoxelGrid:
    """Sparse voxel grid (integer cells, Blender axes, z up). Only exposed faces are meshed."""

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int, int], str] = {}

    def set(self, x: int, y: int, z: int, color: str) -> None:
        self.cells[(x, y, z)] = color

    def remove(self, x: int, y: int, z: int) -> None:
        self.cells.pop((x, y, z), None)

    def get(self, x: int, y: int, z: int) -> str | None:
        return self.cells.get((x, y, z))

    def fill(self, x0: int, y0: int, z0: int, x1: int, y1: int, z1: int, color: str) -> None:
        """Fill the half-open box [x0, x1) × [y0, y1) × [z0, z1)."""
        for x in range(x0, x1):
            for y in range(y0, y1):
                for z in range(z0, z1):
                    self.cells[(x, y, z)] = color

    def mesh(self, origin: Vec = (0.0, 0.0, 0.0),
             face_color: Callable[[tuple[int, int, int], str, str], str] | None = None) -> MeshBuilder:
        """Mesh exposed faces. `origin` is the world position of cell (0,0,0)'s min corner.

        face_color(cell, cell_color, face_key) may remap colors per face (e.g. checker patterns).
        """
        s = CTX.voxel_size
        builder = MeshBuilder()
        for (x, y, z), color in self.cells.items():
            for key, (normal, corners) in _FACES.items():
                if (x + normal[0], y + normal[1], z + normal[2]) in self.cells:
                    continue
                pts = [(origin[0] + (x + c[0]) * s, origin[1] + (y + c[1]) * s, origin[2] + (z + c[2]) * s)
                       for c in corners]
                builder.polygon(pts, face_color((x, y, z), color, key) if face_color else color)
        return builder


def empty(name: str, location: Vec = (0.0, 0.0, 0.0), rotation_deg: Vec = (0.0, 0.0, 0.0),
          parent: bpy.types.Object | None = None, size: float = 0.15) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = size
    obj.location = location
    obj.rotation_euler = Euler([math.radians(a) for a in rotation_deg])
    return link(obj, parent)


def mark_part(obj: bpy.types.Object, name: str) -> bpy.types.Object:
    """Label a mesh for deterministic design_intent structural checks."""
    if not isinstance(name, str) or not name:
        raise ValueError("semantic part name must be a non-empty string")
    obj["semantic_part"] = name
    return obj


def socket(name: str, location: Vec, rotation_deg: Vec = (0.0, 0.0, 0.0),
           parent: bpy.types.Object | None = None, type: str = "generic") -> bpy.types.Object:
    """Attachment point exported as an empty named `socket_<name>` (a Node3D in Godot).

    The mounted component's +Z will follow the socket's +Z. Common rotations (degrees):
      roof / floor (up)            (0, 0, 0)
      axle facing −Y (front)       (90, 0, 0)
      axle facing −X / +X          (0, -90, 0) / (0, 90, 0)
      wall_base, wall on +Y side   (0, 0, 0);  wall on +X: (0, 0, 90);  on −X: (0, 0, -90);  on −Y: (0, 0, 180)
    """
    obj = empty(f"socket_{name}", location, rotation_deg, parent)
    obj["socket"] = name
    obj["socket_type"] = type
    return obj


def loop_frames() -> int:
    return LOOP_FRAMES


def spin_animation(obj: bpy.types.Object, name: str = "spin", *, axis: int = 2, turns: float = 1.0) -> bpy.types.Action:
    """Linear rotation by turns·360° over one loop. Use whole turns (or a multiple of the
    object's rotational symmetry, e.g. k/teeth for a gear) so the loop is seamless."""
    obj.rotation_mode = "XYZ"
    start = obj.rotation_euler[axis]
    obj.keyframe_insert("rotation_euler", index=axis, frame=0)
    obj.rotation_euler[axis] = start + turns * 2 * math.pi
    obj.keyframe_insert("rotation_euler", index=axis, frame=LOOP_FRAMES)
    obj.rotation_euler[axis] = start
    action = obj.animation_data.action
    action.name = name
    _set_interpolation(action, "LINEAR")
    return action


def periodic_animation(obj: bpy.types.Object, data_path: str, index: int, fn: Callable[[float], float],
                       *, step: int = 2, name: str | None = None) -> bpy.types.Action:
    """Sample fn(t) for t in [0, 1] (t = position in the loop) into linear keyframes.

    fn must be periodic: fn(0) == fn(1). Example: a bulge wave running along pipe segments.
    """
    prop = getattr(obj, data_path)
    rest = prop[index]
    for frame in range(0, LOOP_FRAMES + 1, step):
        prop[index] = fn(frame / LOOP_FRAMES)
        obj.keyframe_insert(data_path, index=index, frame=frame)
    prop[index] = rest
    action = obj.animation_data.action
    if name:
        action.name = name
    _set_interpolation(action, "LINEAR")
    return action


def particles(parent: bpy.types.Object, name: str, origin: Vec, *, count: int = 8,
              colors: Sequence[str] = ("wood",), velocity: Vec = (0.0, 0.0, 1.0), spread: float = 0.3,
              gravity: float = 0.0, size: float = 0.04, cycles: int = 4, life: float = 1.0,
              profile: str = "shrink", burst: bool = False, phase: float = 0.0,
              floor: float | None = None, up: int = 2, seed: int = 1) -> list[bpy.types.Object]:
    """Baked particle stream: glTF has no particle systems, so these are small animated cubes.

    Each of `count` cubes is emitted from `origin` (parent-local metres) `cycles` times per loop.
    `velocity` and `gravity` (Z) are in metres per emission cycle; `spread` adds a seeded random
    velocity per particle. For the first `life` of its cycle a particle flies and either shrinks
    away (`profile="shrink"`: sparks, sawdust) or grows and fades (`"puff"`: steam, smoke); the
    rest of the cycle it is hidden, so re-emission never pops. A stream spreads emissions evenly;
    `burst=True` fires all at once at loop time `phase` (an impact). `floor` stops falling
    particles on the ground instead of letting them sink. `up` is the parent axis gravity and
    `floor` act along: 2 (Z) on the floor, 1 (Y) on a wall-plate socket. Level 3 only.
    """
    import random

    rng = random.Random(seed)
    base = Vector(origin)
    made: list[bpy.types.Object] = []
    for i in range(count):
        v = Vector(velocity) + Vector([rng.uniform(-spread, spread) for _ in range(3)])
        lag = rng.uniform(0.0, 0.06) if burst else i / count
        s = size * rng.uniform(0.7, 1.3)
        m = MeshBuilder()
        m.box((-s / 2, -s / 2, -s / 2), (s / 2, s / 2, s / 2), colors[i % len(colors)])
        obj = m.to_object(f"{name}_{i:02d}", parent=parent, location=tuple(base), semantic_part="particles")

        def age(t: float, lag: float = lag) -> float:
            return (t * cycles - phase * cycles - lag) % 1.0 / life

        def where(t: float, axis: int, v: Vector = v, s: float = s) -> float:
            a = min(age(t), 1.0)
            value = base[axis] + v[axis] * a * life + (0.5 * gravity * (a * life) ** 2 if axis == up else 0.0)
            return max(value, floor + s / 2) if axis == up and floor is not None else value

        def scale(t: float) -> float:
            a = age(t)
            if a >= 1.0:
                return 1e-3
            return max(1e-3, math.sin(math.pi * a) if profile == "puff" else 1.0 - a)

        for axis in range(3):
            periodic_animation(obj, "location", axis, lambda t, axis=axis: where(t, axis), name=f"{name}_{i:02d}")
            periodic_animation(obj, "scale", axis, scale)
        made.append(obj)
    return made


def _set_interpolation(action: bpy.types.Action, mode: str) -> None:
    for fcurve in iter_fcurves(action):
        for point in fcurve.keyframe_points:
            point.interpolation = mode


def iter_fcurves(action: bpy.types.Action) -> Iterable[bpy.types.FCurve]:
    """F-curves of an action for both layered (Blender 4.4+/5.x) and legacy actions."""
    layers = getattr(action, "layers", None)
    if layers:
        for layer in layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    yield from bag.fcurves
        return
    yield from getattr(action, "fcurves", [])
