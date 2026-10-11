"""Reusable rectangular vehicle lamps; geometry is independent of Blender.

Local Z is the outward normal, and Z=0 is the mounting plane.  The same
envelope survives all three refinement stages; only the inset lens changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

Point = tuple[float, float, float]

LENS_COLORS = {"head": "lamp_yellow", "tail": "lamp_red", "marker": "lamp_amber"}
SWATCH_COLORS = ("paint_gray", "olive", "metal_steel", "metal_dark", "rubber",
                 "glass_tinted", "lamp_yellow", "lamp_red", "lamp_amber")


@dataclass(frozen=True)
class LampBox:
    name: str
    part: str
    lo: Point
    hi: Point
    color: str


@dataclass(frozen=True)
class LampSpec:
    stage: int
    kind: str
    bounds: tuple[Point, Point]
    boxes: tuple[LampBox, ...]

    @property
    def lens(self) -> LampBox | None:
        return next((box for box in self.boxes if box.part == "lens"), None)


def lamp_spec(params: Mapping[str, Any]) -> LampSpec:
    """Derive a lamp from its mounting face and outer bounds.

    The bezel is a four-sided rectangular opening, rather than a colored
    rectangle coplanar with a solid housing.  Its backplate supports the
    inset lens, so no floating insert or coincident differently colored
    front faces are needed.
    """
    stage = int(params.get("stage", 3))
    kind = str(params.get("kind", "head"))
    width = float(params.get("width", .25))
    height = float(params.get("height", .1875))
    depth = float(params.get("depth", .0625))
    if stage not in (1, 2, 3):
        raise ValueError("lamp stage must be 1, 2 or 3")
    if kind not in LENS_COLORS:
        raise ValueError(f"unknown lamp kind {kind!r}")
    if not (.125 <= width <= .5 and .125 <= height <= .375 and .0625 <= depth <= .125):
        raise ValueError("lamp dimensions exceed the declared component envelope")

    x0, x1, y0, y1 = -width / 2, width / 2, -height / 2, height / 2
    bounds = ((x0, y0, 0.), (x1, y1, depth))
    body_color = "paint_gray" if stage < 3 else str(params.get("body_color", "metal_dark"))
    if stage == 1:
        return LampSpec(stage, kind, bounds, (LampBox("housing", "housing", *bounds, body_color),))

    # Border centers are derived from the face's edges; small lamps keep a
    # positive aperture instead of losing it to a fixed border thickness.
    margin = min(.03125, width / 4, height / 4)
    ix0, ix1, iy0, iy1 = x0 + margin, x1 - margin, y0 + margin, y1 - margin
    back_top = depth / 4
    front = depth if stage == 2 else depth * .75
    lens_color = "steel_dark" if stage == 2 else LENS_COLORS[kind]
    boxes = [LampBox("backplate", "housing", (x0, y0, 0.), (x1, y1, back_top), body_color)]
    if stage == 3:
        boxes.extend((
            LampBox("bezel_left", "housing", (x0, y0, back_top), (ix0, y1, depth), body_color),
            LampBox("bezel_right", "housing", (ix1, y0, back_top), (x1, y1, depth), body_color),
            LampBox("bezel_bottom", "housing", (ix0, y0, back_top), (ix1, iy0, depth), body_color),
            LampBox("bezel_top", "housing", (ix0, iy1, back_top), (ix1, y1, depth), body_color),
        ))
    boxes.append(LampBox("lens", "lens", (ix0, iy0, back_top), (ix1, iy1, front), lens_color))
    return LampSpec(stage, kind, bounds, tuple(boxes))


def render_lamp(params: Mapping[str, Any]):  # noqa: ANN201
    """Build separate housing and emitter meshes; emission survives GLB export."""
    import voxlib as vx

    spec = lamp_spec(params)
    root = vx.empty("zk_lamp")
    housing = vx.MeshBuilder()
    for box in spec.boxes:
        if box.part == "housing":
            housing.box(box.lo, box.hi, box.color)
    housing.to_object("lamp_housing", parent=root, semantic_part="housing")
    if spec.lens is not None:
        lens = spec.lens
        mesh = vx.MeshBuilder()
        mesh.box(lens.lo, lens.hi, lens.color)
        obj = mesh.to_object("lamp_lens", parent=root, semantic_part="lens")
        if spec.stage >= 3:
            vx.palette_emission(obj, lens.color)
    root["lamp_kind"] = spec.kind
    root["refinement_stage"] = spec.stage
    return root


def swatch_specs() -> tuple[LampBox, ...]:
    """Nine material samples anchored to one half-metre repeat grid."""
    half = .1875
    middle = (len(SWATCH_COLORS) - 1) / 2
    return tuple(
        LampBox(f"swatch_{index:02d}_{color}", "swatches",
                ((index - middle) * .5 - half, -half, 0.),
                ((index - middle) * .5 + half, half, 2 * half), color)
        for index, color in enumerate(SWATCH_COLORS)
    )


def render_swatches():  # noqa: ANN201
    import voxlib as vx

    root = vx.empty("zk_materials")
    for sample in swatch_specs():
        mesh = vx.MeshBuilder()
        mesh.box(sample.lo, sample.hi, sample.color)
        obj = mesh.to_object(sample.name, parent=root, semantic_part="swatches")
        obj["palette_color"] = sample.color
        if sample.color in LENS_COLORS.values():
            vx.palette_emission(obj, sample.color)
    return root
