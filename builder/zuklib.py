"""Shared metric skeleton for the Zuk sheet study's reusable kit.

Blender metres: X right, front -Y, Z up. All plans use truck space; exported
components may subtract an ANCHORS entry, and assembly restores that same anchor.
Study stages 1/2/3 mean massing/+10/+10; they are independent of Registry's
complexity level (level 3 enables the running gear demonstration loop).
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

CAB_LO, CAB_HI = (-1., -1.75, .75), (1., -.5, 2.5)
NOSE_LO, NOSE_HI = (-1., -2.25, .75), (1., -1.75, 1.5)
BODY_LO, BODY_HI = (-1., -.5, .75), (1., 2.25, 2.5)
CHASSIS_LO, CHASSIS_HI = (-.75, -2.25, .5), (.75, 2.25, .75)
AXLES = {"front": -1.25, "rear": 1.5}
WHEEL_R, WHEEL_WIDTH, WHEEL_X = .375, .5, 1.
SUSPENSION_TOP = .625
ARCH_HALF_LENGTH, ARCH_TOP, ARCH_INNER_X = .5625, 1., .6875
ANCHORS = {
    "cab": (0., AXLES["front"], 0.),
    "body": (0., 0., 0.),
    "axle_front": (0., AXLES["front"], 0.),
    "axle_rear": (0., AXLES["rear"], 0.),
}
FRONT_LAMPS = {"head_left": (-.75, NOSE_LO[1], 1.125),
               "head_right": (.75, NOSE_LO[1], 1.125)}
REAR_LAMPS = {"tail_left": (-.875, BODY_HI[1], 1.125),
              "tail_right": (.875, BODY_HI[1], 1.125)}
DEFAULTS = {"stage": 3, "paint": "paint_gray", "finish": True,
            "service_panel": "compact", "wheel_fit": "legacy"}


@dataclass(frozen=True, slots=True)
class Layout:
    """One immutable fit contract shared by body, chassis and running gear."""

    wheel_width: float
    wheel_x: float
    arch_half_length: float
    arch_top: float
    arch_chamfer: float
    body_bottom: float
    rail_inner: float
    rail_outer: float
    suspension_x: float


LAYOUTS = {
    "legacy": Layout(.5, 1., .5625, 1., 0., .75, .5, .5625, .625),
    "inset": Layout(.25, .75, .5, 1., .1875, .5, .375, .4375, .375),
}


def layout(params: Mapping | None = None) -> Layout:
    """Legacy is the default; an explicit new branch changes the wheel fit."""
    name = (params or {}).get("wheel_fit", "legacy")
    try:
        return LAYOUTS[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown Zuk wheel fit: {name!r}") from exc
DETAIL_GROUPS = {
    2: ("D01 wheels", "D02 wheel openings", "D03 one-piece windscreen",
        "D04 side windows", "D05 cab doors", "D06 rear doors",
        "D07 three grille bars", "D08 head lamps", "D09 front bumper",
        "D10 rear bumper"),
    3: ("D11 mirrors", "D12 wipers", "D13 cab handles", "D14 rear handles",
        "D15 rear hinges", "D16 wheel hubs", "D17 tail lamps", "D18 steps",
        "D19 three side ribs", "D20 service panels"),
}


def gltf(point):
    """Transform a Blender point into Registry/glTF interface coordinates."""
    x, y, z = point
    return (x, z, -y)


def color(stage: int, role: str, paint: str = "paint_gray", finish: bool = True) -> str:
    """Reuse Registry surface classes; massing/sheet comparisons stay neutral."""
    plain = {"paint": "paint_gray", "metal": "steel_dark", "trim": "soot",
             "glass": "steel_dark", "tire": "soot", "head": "steel",
             "tail": "steel_dark"}
    rich = {"paint": paint, "metal": "metal_dark", "trim": "plastic",
            "glass": "glass_tinted", "tire": "rubber", "head": "lamp_yellow",
            "tail": "lamp_red"}
    return (rich if stage >= 3 and finish else plain)[role]
