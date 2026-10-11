"""Blender Eevee implementation of the procedural toon model (see _base.md).

API used by builder/material_build.py:
    build(params, ctx) -> bpy.types.Material        surface material (emission of the toon color)
    decorate(objects, params, ctx) -> None           outlines: Solidify hull or Freestyle lines
ctx: {"sun_energy": float, "sun_dir": (x, y, z) toward the light, "resolution": int}
"""

from __future__ import annotations

import math
from typing import Any

import bpy


def _lin(hex_color: str) -> tuple[float, float, float, float]:
    """#rrggbb (sRGB) → linear RGBA for node sockets."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


class _G:
    """Tiny node-graph helper."""

    def __init__(self, mat: bpy.types.Material):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def node(self, kind: str, **props: Any) -> bpy.types.Node:
        n = self.nt.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a: Any, b: Any) -> None:
        self.nt.links.new(a, b)

    def math(self, op: str, a: Any, b: Any = None, clamp: bool = False) -> Any:
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]

    def smoothstep(self, x: Any, e0: float, e1: float) -> Any:
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        self.link(x, n.inputs["Value"])
        n.inputs["From Min"].default_value = e0
        n.inputs["From Max"].default_value = max(e1, e0 + 1e-4)
        return n.outputs["Result"]

    def vec(self, op: str, a: Any, b: Any = None) -> bpy.types.Node:
        n = self.node("ShaderNodeVectorMath", operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n

    def mix(self, blend: str, fac: Any, a: Any, b: Any) -> Any:
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_result=False)
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, (int, float)):
                sock.default_value = float(v)
            elif isinstance(v, tuple):
                sock.default_value = v
            else:
                self.link(v, sock)
        return n.outputs[2]


def build(params: dict[str, Any], ctx: dict[str, Any]) -> bpy.types.Material:
    mat = bpy.data.materials.new("toon")
    mat.use_nodes = True
    g = _G(mat)
    s = max(params["softness"], 1e-4)
    s2 = params["softness"] * 0.5 + 0.005

    # L = saturate(N·L)·shadow, recovered from Eevee's diffuse (energy/π · cosθ · shadow)
    diffuse = g.node("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (1, 1, 1, 1)
    s2rgb = g.node("ShaderNodeShaderToRGB")
    g.link(diffuse.outputs[0], s2rgb.inputs[0])
    bw = g.node("ShaderNodeRGBToBW")
    g.link(s2rgb.outputs["Color"], bw.inputs[0])
    L = g.math("MULTIPLY", bw.outputs[0], math.pi / ctx["sun_energy"], clamp=True)
    x = g.math("ADD", L, params["band_bias"], clamp=True)

    n = params["bands"]
    if n <= 1:
        t: Any = g.math("ADD", 1.0, 0.0)
    else:
        acc: Any = None
        for k in range(1, n):
            step = g.smoothstep(x, k / n - s, k / n + s)
            acc = step if acc is None else g.math("ADD", acc, step)
        t = g.math("DIVIDE", acc, n - 1)

    dark = tuple(1 + (c - 1) * params["shadow_strength"] for c in _lin(params["shadow_color"])[:3]) + (1.0,)
    tint = _lin(params["light_tint"])
    shade = g.mix("MIX", t, dark, tint)

    geo = g.node("ShaderNodeNewGeometry")
    if params["halftone"] > 0:
        coords = g.node("ShaderNodeTexCoord")
        px = g.vec("MULTIPLY", coords.outputs["Window"], (ctx["resolution"] / params["halftone_scale"],) * 3)
        cell = g.vec("SUBTRACT", g.vec("FRACTION", px.outputs[0]).outputs[0], (0.5, 0.5, 0.0))
        sep = g.node("ShaderNodeSeparateXYZ")
        g.link(cell.outputs[0], sep.inputs[0])
        r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", sep.outputs[0], sep.outputs[0]),
                                  g.math("MULTIPLY", sep.outputs[1], sep.outputs[1])))
        radius = g.math("MULTIPLY", g.math("SQRT", g.math("SUBTRACT", 1.0, t)), 0.7 * params["halftone"])
        inside = g.math("SUBTRACT", 1.0, g.smoothstep(g.math("SUBTRACT", r, radius), -0.05, 0.05))
        shade = g.mix("MULTIPLY", g.math("MULTIPLY", inside, 0.55), shade, (0.0, 0.0, 0.0, 1.0))

    albedo = g.node("ShaderNodeVertexColor")          # empty layer name → active color attribute
    color = g.mix("MULTIPLY", 1.0, albedo.outputs["Color"], shade)

    # specular: N·H with the known sun direction
    if params["specular"] > 0:
        view = geo.outputs["Incoming"]
        h = g.vec("NORMALIZE", g.vec("ADD", view, tuple(ctx["sun_dir"])).outputs[0])
        ndh = g.vec("DOT_PRODUCT", geo.outputs["Normal"], h.outputs[0]).outputs["Value"]
        th = 1 - params["specular_size"] / 2
        lit = g.math("GREATER_THAN", L, 0.01)
        spec = g.math("MULTIPLY", g.math("MULTIPLY", g.smoothstep(ndh, th - s2, th + s2), lit), params["specular"])
        color = g.mix("ADD", spec, color, tint)

    if params["rim"] > 0:
        ndv = g.math("ABSOLUTE", g.vec("DOT_PRODUCT", geo.outputs["Normal"], geo.outputs["Incoming"]).outputs["Value"])
        edge = g.smoothstep(g.math("SUBTRACT", 1.0, ndv), 1 - params["rim_width"] - s2, 1 - params["rim_width"] + s2)
        rimf = g.math("MULTIPLY", g.math("MULTIPLY", edge, params["rim"]),
                      g.math("ADD", 0.35, g.math("MULTIPLY", t, 0.65)))
        color = g.mix("ADD", rimf, color, _lin(params["rim_color"]))

    emission = g.node("ShaderNodeEmission")
    g.link(color, emission.inputs["Color"])
    emission.inputs["Strength"].default_value = 1.0
    out = g.node("ShaderNodeOutputMaterial")
    g.link(emission.outputs[0], out.inputs["Surface"])
    return mat


def decorate(objects: list[bpy.types.Object], params: dict[str, Any], ctx: dict[str, Any]) -> None:
    mode = params["outline_mode"]
    if mode == "hull" and params["outline_width"] > 0:
        shell = bpy.data.materials.new("toon_outline")
        shell.use_nodes = True
        shell.use_backface_culling = True
        nodes = shell.node_tree.nodes
        nodes.clear()
        em = nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = _lin(params["outline_color"])
        out = nodes.new("ShaderNodeOutputMaterial")
        shell.node_tree.links.new(em.outputs[0], out.inputs["Surface"])
        for obj in objects:
            obj.data.materials.append(shell)
            mod = obj.modifiers.new("outline", "SOLIDIFY")
            mod.thickness = params["outline_width"]
            mod.offset = 1.0
            mod.use_flip_normals = True
            mod.use_rim = False
            mod.use_even_offset = False       # even offset spikes on welded voxel corners
            mod.use_quality_normals = True
            mod.material_offset = len(obj.data.materials) - 1
    elif mode == "screen":
        scene = bpy.context.scene
        scene.render.use_freestyle = True
        scene.render.line_thickness_mode = "ABSOLUTE"
        scene.render.line_thickness = 1.0                  # unit; the style thickness multiplies it
        layer = bpy.context.view_layer
        layer.use_freestyle = True
        settings = layer.freestyle_settings
        settings.crease_angle = math.radians(140)
        lineset = settings.linesets[0] if settings.linesets else settings.linesets.new("toon")
        lineset.select_by_visibility = True
        lineset.select_by_edge_types = True
        lineset.select_silhouette = True
        lineset.select_border = True
        lineset.select_crease = True
        if lineset.linestyle is None:                      # background mode creates linesets without a style
            lineset.linestyle = bpy.data.linestyles.new("toon_line")
        lineset.linestyle.color = _lin(params["outline_color"])[:3]
        lineset.linestyle.thickness = params["outline_px"] * ctx["resolution"] / 512
