"""Isometric and six orthographic PNG views with consistent scale and lighting."""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Euler, Vector
from projection_views import PROJECTION_VIEWS, projection_scale

VIEWS: dict[str, tuple[float, float, float]] = {
    "iso": (math.radians(54.7356), 0.0, math.radians(45.0)),   # classic isometric, from front-right
    **PROJECTION_VIEWS,
}
# Characters face −Y: a model sheet at eye height plus a 3/4 view close to the game camera.
CHARACTER_VIEWS: dict[str, tuple[float, float, float]] = {
    **PROJECTION_VIEWS,
    "34": (math.radians(78.0), 0.0, math.radians(35.0)),
    "side": (math.radians(90.0), 0.0, math.radians(90.0)),
}
BACKGROUND = (0.32, 0.33, 0.35)
# Canonical key light, direction TOWARD the light in Blender axes (front-left-top). In the iso view
# the façade (−Y), the roof and the right side (+X) land in three different light levels.
# The web viewer uses the same direction (glTF: x, z, −y).
SUN_DIRECTION = Vector((-0.45, -0.55, 0.70)).normalized()


def _setup_scene(size: int, sun_energy: float = 3.0, world_lights: bool = True) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0          # legacy files may carry their own exposure/gamma
    scene.view_settings.gamma = 1.0
    eevee = scene.eevee
    if hasattr(eevee, "taa_render_samples"):
        eevee.taa_render_samples = 16

    world = bpy.data.worlds.new("preview_world")
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    background = nodes.get("Background")
    background.inputs["Color"].default_value = (*BACKGROUND, 1.0)
    background.inputs["Strength"].default_value = 1.0
    if not world_lights:
        # background visible to the camera but contributes no light (toon materials own their shading)
        dark = nodes.new("ShaderNodeBackground")
        dark.inputs["Strength"].default_value = 0.0
        path = nodes.new("ShaderNodeLightPath")
        mix = nodes.new("ShaderNodeMixShader")
        out = nodes.get("World Output")
        links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
        links.new(dark.outputs[0], mix.inputs[1])
        links.new(background.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs["Surface"])
    scene.world = world

    sun_data = bpy.data.lights.new("preview_sun", "SUN")
    sun_data.energy = sun_energy
    sun_data.angle = math.radians(6)
    sun = bpy.data.objects.new("preview_sun", sun_data)
    sun.rotation_euler = SUN_DIRECTION.to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(sun)
    # A weak opposite light keeps rear and underside projections legible.
    fill_data = bpy.data.lights.new("preview_fill", "SUN")
    fill_data.energy = sun_energy * 0.3
    fill = bpy.data.objects.new("preview_fill", fill_data)
    fill.rotation_euler = (-SUN_DIRECTION).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(fill)


def render(out_dir: Path, size: int, lo: Vector, hi: Vector, hidden: list[bpy.types.Object], *,
           sun_energy: float = 3.0, world_lights: bool = True,
           views: dict[str, tuple[float, float, float]] | None = None, prefix: str = "preview_") -> dict[str, str]:
    _setup_scene(size, sun_energy, world_lights)
    for obj in hidden:
        obj.hide_render = True

    cam_data = bpy.data.cameras.new("preview_cam")
    cam_data.type = "ORTHO"
    cam_data.clip_start = 0.01
    cam_data.clip_end = 500.0
    cam = bpy.data.objects.new("preview_cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    center = (lo + hi) / 2
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    radius = max((c - center).length for c in corners) or 1.0
    files: dict[str, str] = {}
    for name, rotation in (VIEWS if views is None else views).items():
        rot = Euler(rotation).to_matrix()
        forward = rot @ Vector((0.0, 0.0, -1.0))
        cam.rotation_euler = Euler(rotation)
        cam.location = center - forward * (radius * 4 + 5)
        inv = rot.transposed()
        extent = max(max(abs((inv @ (c - center)).x), abs((inv @ (c - center)).y)) for c in corners)
        cam_data.ortho_scale = (projection_scale(lo, hi) if name in PROJECTION_VIEWS or name == "side"
                               else max(extent * 2 * 1.18, 0.5))
        filename = f"{prefix}{name}.png"
        bpy.context.scene.render.filepath = str(out_dir / filename)
        bpy.ops.render.render(write_still=True)
        files[name] = filename
    return files
