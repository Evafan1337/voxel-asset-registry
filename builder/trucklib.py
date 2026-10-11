"""Modular truck kit (mt_*): the skeleton every block of the kit shares.

Blocks are blockout plans (builder/blockout.py) authored in truck space and drawn by
`vehlib.render(plan, origin=ANCHORS[...])`: the object origin is the block's mount point on the
road (z = 0) under its anchor, so heights stay absolute and a block docks on the chassis socket of
the same name with no further offsets. The chassis makes its sockets from the very same anchors —
one anchor for both sides of every joint.

Front −Y, the left side +X carries the fuel tank, the tool box and the exhaust stack; three axles:
one in front, a tandem behind. Pure Python: tests read the plans without Blender. Changing this
file changes every mt_* block: bump their generator_version."""

from __future__ import annotations

try:
    from .blockout import DETAIL_GRID as D, MACRO_GRID as M
except ImportError:  # top-level import inside Blender (builder/ on sys.path)
    from blockout import DETAIL_GRID as D, MACRO_GRID as M

WHEEL_R = 2 * M                    # the axles sit at z = WHEEL_R
WHEEL_W = 5 * D
WHEEL_X = 4 * M                    # outer wheel centre plane; a twin sits WHEEL_W + D inboard
AXLES = {"front": -13 * M, "rear_1": 7 * M, "rear_2": 12 * M}

FRAME_W, FRAME_Y, FRAME_Z = 2 * M, (-14 * M, 15 * M), (2 * M, 4 * M)     # front end inside the bonnet
RAIL_X = (FRAME_W - 4 * D, FRAME_W - D)          # rails inboard of the twin wheels
CAB_FLOOR = FRAME_Z[1]                           # the cab sits on the rails
BOX_FLOOR = FRAME_Z[1] + M                       # the cargo box sits on a subframe

CAB_W, CAB_Y, CAB_TOP = 5 * M, (-11 * M, -5 * M), 11 * M
NOSE_Y = (-15 * M, CAB_Y[0])
BOX_W, BOX_Y, BOX_TOP = 5 * M, (-3 * M, 15 * M), 13 * M

ANCHORS = {                                      # chassis sockets on the road, mount points of the blocks
    "cab": (0.0, CAB_Y[0], 0.0),
    "box": (0.0, (BOX_Y[0] + BOX_Y[1]) / 2, 0.0),
    "axle_front": (0.0, AXLES["front"], 0.0),
    "axle_rear_1": (0.0, AXLES["rear_1"], 0.0),
    "axle_rear_2": (0.0, AXLES["rear_2"], 0.0),
    "exhaust": (4 * M, -4 * M, 0.0),
    "tank": (3 * M, -1 * M, 0.0),
    "toolbox": (3 * M, 3 * M, 0.0),
}


def finish(stage: int, plain: str, rich: str) -> str:
    """Surface finish by stage: flat paint up to DETAIL, the real material (chrome, dark metal) at
    GAME — the reference's v1 → v3 is the same mesh with more detail, then real-time materials."""
    return rich if stage >= 5 else plain


def mirror(sx: int, x0: float, x1: float) -> tuple[float, float]:
    """x range of a part on side sx (+1 left / +X, −1 right / −X) given its +X range."""
    return (x0, x1) if sx > 0 else (-x1, -x0)
