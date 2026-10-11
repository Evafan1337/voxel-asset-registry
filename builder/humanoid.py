"""Humanoid v1: the one skeleton, proportions and animation set shared by every character.

Pure Python — tests read it without Blender; builder/charlib.py turns it into an Armature,
skinned meshes and actions. Blender axes: Z up, the character faces −Y, its left side is +X
(".L" bones). The rest pose is an A-pose (arms 42° below horizontal); clips are authored as
semantic channels (pitch, swing, abduct, bend …) in degrees and metres, so the same clip plays on
every body. Feet are placed by an analytic two-bone leg solve at authoring time (no runtime IK).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

RIG = "humanoid_v1"
FPS = 24
A_POSE = math.radians(42.0)                      # arms below horizontal in the rest pose

# name, parent, connected to the parent's tail
BONES: tuple[tuple[str, str | None, bool], ...] = (
    ("root", None, False),
    ("pelvis", "root", False),
    ("spine", "pelvis", True),
    ("chest", "spine", True),
    ("neck", "chest", True),
    ("head", "neck", True),
    ("upper_arm.L", "chest", False), ("forearm.L", "upper_arm.L", True), ("hand.L", "forearm.L", True),
    ("upper_arm.R", "chest", False), ("forearm.R", "upper_arm.R", True), ("hand.R", "forearm.R", True),
    ("thigh.L", "pelvis", False), ("shin.L", "thigh.L", True), ("foot.L", "shin.L", True),
    ("thigh.R", "pelvis", False), ("shin.R", "thigh.R", True), ("foot.R", "shin.R", True),
)
REQUIRED_BONES = tuple(name for name, _p, _c in BONES)
CLIPS: dict[str, int] = {"idle": 48, "walk": 32, "talk": 96, "work": 48, "celebrate": 48}   # frames @24 fps
BODY_TYPES = {"slim": 0.84, "average": 1.0, "heavy": 1.22}

Vec = tuple[float, float, float]


# ---------------------------------------------------------------------------------- proportions
@dataclass(frozen=True)
class Body:
    height: float
    width: float           # body_type factor (torso, limbs)
    shoulder: float        # shoulder_width factor
    head_h: float
    neck_h: float
    ankle_z: float
    knee_z: float
    hip_z: float
    waist_z: float
    chest_z: float
    shoulder_z: float
    chin_z: float
    hip_x: float
    shoulder_x: float
    upper_arm: float
    forearm: float
    hand: float
    foot: float
    arm_z: float | None = None   # shoulder joint height (template bodies); None: shoulder_z − 0.02·height
    arm_y: float = 0.0           # shoulder joint depth (template bodies keep their shoulders' own offset)

    @property
    def leg(self) -> float:
        return self.hip_z - self.ankle_z

    @property
    def thigh(self) -> float:
        return self.hip_z - self.knee_z

    @property
    def shin(self) -> float:
        return self.knee_z - self.ankle_z


def body(params: dict) -> Body:
    """Proportions from the character params: the crown ends exactly at `height` (hair may add)."""
    H = float(params["height"])
    width = BODY_TYPES[params.get("body_type", "average")]
    shoulder = float(params.get("shoulder_width", 1.0))
    head_h = 0.235 * H * float(params.get("head_scale", 1.15)) / 1.15
    neck_h = 0.028 * H
    ankle = 0.06 * H
    avail = H - head_h - neck_h - ankle
    leg = min(avail * 0.57 * float(params.get("leg_length", 1.0)), avail * 0.68)
    torso = avail - leg
    hip = ankle + leg
    shoulder_z = hip + torso
    return Body(
        height=H, width=width, shoulder=shoulder, head_h=head_h, neck_h=neck_h,
        ankle_z=ankle, knee_z=ankle + leg * 0.5, hip_z=hip,
        waist_z=hip + 0.30 * torso, chest_z=hip + 0.62 * torso, shoulder_z=shoulder_z,
        chin_z=shoulder_z + neck_h, hip_x=0.058 * H * min(width, 1.1), shoulder_x=0.108 * H * shoulder,
        upper_arm=0.155 * H, forearm=0.14 * H, hand=0.07 * H, foot=0.15 * H,
    )


def arm_dir(side: int) -> Vec:
    return (side * math.cos(A_POSE), 0.0, -math.sin(A_POSE))


def skeleton(b: Body) -> dict[str, tuple[Vec, Vec]]:
    """Rest-pose (A-pose) head and tail of every bone, Blender armature space."""
    joints: dict[str, tuple[Vec, Vec]] = {
        "root": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.1 * b.height)),
        "pelvis": ((0.0, 0.0, b.hip_z), (0.0, 0.0, b.waist_z)),
        "spine": ((0.0, 0.0, b.waist_z), (0.0, 0.0, b.chest_z)),
        "chest": ((0.0, 0.0, b.chest_z), (0.0, 0.0, b.shoulder_z)),
        "neck": ((0.0, 0.0, b.shoulder_z), (0.0, 0.0, b.chin_z)),
        "head": ((0.0, 0.0, b.chin_z), (0.0, 0.0, b.chin_z + b.head_h)),
    }
    for side, tag in ((1, "L"), (-1, "R")):
        d = arm_dir(side)
        sh = (side * b.shoulder_x, b.arm_y, b.shoulder_z - 0.02 * b.height if b.arm_z is None else b.arm_z)
        el = tuple(sh[i] + d[i] * b.upper_arm for i in range(3))
        wr = tuple(el[i] + d[i] * b.forearm for i in range(3))
        tip = tuple(wr[i] + d[i] * b.hand for i in range(3))
        joints[f"upper_arm.{tag}"] = (sh, el)          # type: ignore[assignment]
        joints[f"forearm.{tag}"] = (el, wr)            # type: ignore[assignment]
        joints[f"hand.{tag}"] = (wr, tip)              # type: ignore[assignment]
        x = side * b.hip_x
        hip, knee, ankle = (x, 0.0, b.hip_z), (x, -0.01 * b.height, b.knee_z), (x, 0.0, b.ankle_z)
        joints[f"thigh.{tag}"] = (hip, knee)
        joints[f"shin.{tag}"] = (knee, ankle)
        joints[f"foot.{tag}"] = (ankle, (x, -0.55 * b.foot, 0.25 * b.ankle_z))
    return joints


# ---------------------------------------------------------------------------------- channels → rotations
def _unit(v: Vec) -> Vec:
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dir(joints: dict, bone: str) -> Vec:
    h, t = joints[bone]
    return _unit((t[0] - h[0], t[1] - h[1], t[2] - h[2]))


FRONT, BACK = (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)
X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
TORSO = ("pelvis", "spine", "chest", "neck", "head")


def rotations(joints: dict, ch: dict[str, float]) -> dict[str, list[tuple[Vec, float]]]:
    """Semantic channels → per bone list of (axis in armature rest space, radians), applied in order.

    Torso bones: pitch (+ forward bend), roll (+ tilt to the left), yaw (+ turn left).
    upper_arm / thigh: swing (+ forward), abduct (+ away from the body), twist.
    forearm / hand: bend (+ toward the front). shin: bend (+ knee flexion, foot backward).
    foot: pitch (+ toe up)."""
    out: dict[str, list[tuple[Vec, float]]] = {}
    r = math.radians
    for bone in TORSO:
        rot = [(Z, r(ch.get(f"{bone}.yaw", 0.0))), (Y, r(ch.get(f"{bone}.roll", 0.0))),
               (X, r(ch.get(f"{bone}.pitch", 0.0)))]
        out[bone] = [a for a in rot if a[1]]
    for side, tag in ((1, "L"), (-1, "R")):
        out[f"upper_arm.{tag}"] = [a for a in (
            ((0.0, -side, 0.0), r(ch.get(f"upper_arm.{tag}.abduct", 0.0))),
            (X, -r(ch.get(f"upper_arm.{tag}.swing", 0.0))),
            (_dir(joints, f"upper_arm.{tag}"), r(ch.get(f"upper_arm.{tag}.twist", 0.0)) * side)) if a[1]]
        for bone in (f"forearm.{tag}", f"hand.{tag}"):
            out[bone] = [a for a in ((_unit(_cross(_dir(joints, bone), FRONT)), r(ch.get(f"{bone}.bend", 0.0))),) if a[1]]
        out[f"thigh.{tag}"] = [a for a in (
            ((0.0, -side, 0.0), r(ch.get(f"thigh.{tag}.abduct", 0.0))),
            (X, -r(ch.get(f"thigh.{tag}.swing", 0.0)))) if a[1]]
        out[f"shin.{tag}"] = [a for a in ((_unit(_cross(_dir(joints, f"shin.{tag}"), BACK)),
                                            r(ch.get(f"shin.{tag}.bend", 0.0))),) if a[1]]
        out[f"foot.{tag}"] = [a for a in ((X, -r(ch.get(f"foot.{tag}.pitch", 0.0))),) if a[1]]
    return out


def pelvis_offset(ch: dict[str, float]) -> Vec:
    return (ch.get("pelvis.x", 0.0), ch.get("pelvis.y", 0.0), ch.get("pelvis.z", 0.0))


# ---------------------------------------------------------------------------------- feet on the ground
def solve_leg(b: Body, ch: dict[str, float], tag: str, ankle: Vec | None = None) -> None:
    """Set thigh swing, knee bend and foot pitch so the ankle reaches `ankle` (rest ankle = planted)
    from the hip moved by the pelvis offset; the foot stays level. Unreachable → straight leg."""
    side = 1 if tag == "L" else -1
    px, py, pz = pelvis_offset(ch)
    hip = (side * b.hip_x + px, py, b.hip_z + pz)
    target = ankle or (side * b.hip_x, 0.0, b.ankle_z)
    vy, vz = target[1] - hip[1], target[2] - hip[2]
    a, c = b.thigh, b.shin
    d = min(math.hypot(vy, vz), (a + c) * 0.999)
    phi = math.atan2(-vy, -vz)                                  # forward of straight down
    alpha = math.acos(max(-1.0, min(1.0, (a * a + d * d - c * c) / (2 * a * d))))
    knee = math.pi - math.acos(max(-1.0, min(1.0, (a * a + c * c - d * d) / (2 * a * c))))
    pelvis_pitch = ch.get("pelvis.pitch", 0.0)
    swing = math.degrees(phi + alpha) + pelvis_pitch            # a pitched pelvis already swings the thigh
    ch[f"thigh.{tag}.swing"] = swing
    ch[f"shin.{tag}.bend"] = math.degrees(knee)
    ch[f"thigh.{tag}.abduct"] = ch.get(f"thigh.{tag}.abduct", 0.0) + math.degrees(
        math.atan2(side * (target[0] - hip[0]), hip[2] - target[2]))
    ch[f"foot.{tag}.pitch"] = ch.get(f"foot.{tag}.pitch", 0.0) + math.degrees(knee) - (swing - pelvis_pitch)


# ---------------------------------------------------------------------------------- the animation set
def _smooth(u: float) -> float:
    return u * u * (3 - 2 * u)


def _keys(t: float, keys: list[tuple[float, dict[str, float]]]) -> dict[str, float]:
    """Smoothstep between key poses over t ∈ [0, 1); the last key must equal the first (a loop)."""
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            u = _smooth((t - t0) / (t1 - t0)) if t1 > t0 else 0.0
            names = set(p0) | set(p1)
            return {n: p0.get(n, 0.0) + (p1.get(n, 0.0) - p0.get(n, 0.0)) * u for n in names}
    return dict(keys[-1][1])


def _arms_down(ch: dict[str, float], abduct: float = -30.0, bend: float = 14.0) -> dict[str, float]:
    for tag in ("L", "R"):
        ch.setdefault(f"upper_arm.{tag}.abduct", abduct)
        ch.setdefault(f"forearm.{tag}.bend", bend)
    return ch


def idle(b: Body, t: float) -> dict[str, float]:
    w = 2 * math.pi * t
    ch = {
        "pelvis.x": 0.008 * math.sin(w), "pelvis.z": -0.006 - 0.004 * math.sin(2 * w), "pelvis.roll": 1.5 * math.sin(w),
        "spine.roll": -1.2 * math.sin(w), "chest.pitch": -1.0 - 1.5 * math.sin(2 * w),
        "neck.yaw": 3.0 * math.sin(w + 1.0), "head.pitch": 2.0 * math.sin(2 * w + 0.5), "head.roll": -1.5 * math.sin(w),
        "upper_arm.L.swing": 3 + 2 * math.sin(w), "upper_arm.R.swing": 3 - 2 * math.sin(w),
        "upper_arm.L.abduct": -30 + 1.5 * math.sin(2 * w), "upper_arm.R.abduct": -30 + 1.5 * math.sin(2 * w),
    }
    _arms_down(ch)
    for tag in ("L", "R"):
        solve_leg(b, ch, tag)
    return ch


def walk(b: Body, t: float) -> dict[str, float]:
    stride, lift = 0.45 * b.leg, 0.10 * b.leg
    w = 2 * math.pi * t
    ch = {"pelvis.z": -0.045 * b.leg * (0.5 + 0.5 * math.cos(2 * w)), "pelvis.yaw": -5 * math.cos(w),
          "pelvis.roll": 2.5 * math.sin(w), "spine.pitch": 4.0, "chest.yaw": 7 * math.cos(w),
          "neck.yaw": -4 * math.cos(w), "head.pitch": -3.0,
          "upper_arm.L.swing": -24 * math.cos(w), "upper_arm.R.swing": 24 * math.cos(w),
          "forearm.L.bend": 18 + 12 * (1 - math.cos(w)) / 2, "forearm.R.bend": 18 + 12 * (1 + math.cos(w)) / 2}
    _arms_down(ch, abduct=-33.0)
    for tag, phase in (("L", 0.0), ("R", 0.5)):
        side = 1 if tag == "L" else -1
        u = (t + phase) % 1.0
        if u < 0.6:                                               # stance: planted, sliding back under the hip
            y, z, toe = -stride / 2 + stride * u / 0.6, 0.0, 0.0
        else:                                                     # swing: lift and carry forward
            v = (u - 0.6) / 0.4
            y, z = stride / 2 - stride * _smooth(v), lift * math.sin(math.pi * v)
            toe = 18 * math.sin(math.pi * v) - 10 * math.sin(2 * math.pi * v)
        ch[f"foot.{tag}.pitch"] = toe
        solve_leg(b, ch, tag, (side * b.hip_x, y, b.ankle_z + z))
    return ch


def talk(b: Body, t: float) -> dict[str, float]:
    w = 2 * math.pi * t
    ch = {"pelvis.x": 0.006 * math.sin(w), "pelvis.z": -0.008, "pelvis.roll": 1.2 * math.sin(w),
          "chest.yaw": 5 * math.sin(w), "chest.pitch": -2.0,
          "head.pitch": 5 * math.sin(3 * w), "head.yaw": 8 * math.sin(w + 0.6), "head.roll": 4 * math.sin(2 * w),
          "upper_arm.R.swing": 32 + 12 * math.sin(2 * w), "upper_arm.R.abduct": -12 + 6 * math.sin(3 * w),
          "forearm.R.bend": 78 + 18 * math.sin(3 * w), "hand.R.bend": 15 * math.sin(3 * w + 1.0),
          "upper_arm.L.swing": 10 + 8 * math.sin(w + 2.0), "forearm.L.bend": 30 + 15 * math.sin(2 * w + 1.0)}
    _arms_down(ch)
    for tag in ("L", "R"):
        solve_leg(b, ch, tag)
    return ch


_READY = {"upper_arm.L.swing": 45, "upper_arm.R.swing": 45, "upper_arm.L.abduct": -24, "upper_arm.R.abduct": -24,
          "forearm.L.bend": 72, "forearm.R.bend": 72, "spine.pitch": 8, "pelvis.z": -0.03, "head.pitch": 6}
_RAISED = {"upper_arm.L.swing": 155, "upper_arm.R.swing": 155, "upper_arm.L.abduct": -18, "upper_arm.R.abduct": -18,
           "forearm.L.bend": 55, "forearm.R.bend": 55, "spine.pitch": -8, "chest.pitch": -6, "pelvis.z": -0.01,
           "head.pitch": -10}
_STRIKE = {"upper_arm.L.swing": 32, "upper_arm.R.swing": 32, "upper_arm.L.abduct": -22, "upper_arm.R.abduct": -22,
           "forearm.L.bend": 12, "forearm.R.bend": 12, "spine.pitch": 20, "chest.pitch": 10, "pelvis.z": -0.07,
           "head.pitch": 14}
_RECOIL = {"upper_arm.L.swing": 48, "upper_arm.R.swing": 48, "upper_arm.L.abduct": -22, "upper_arm.R.abduct": -22,
           "forearm.L.bend": 32, "forearm.R.bend": 32, "spine.pitch": 13, "chest.pitch": 4, "pelvis.z": -0.055,
           "head.pitch": 8}


def work(b: Body, t: float) -> dict[str, float]:
    """Two strikes per loop: raise over the head → strike down in front → recoil → ready."""
    u = (t * 2) % 1.0
    ch = _keys(u, [(0.0, _READY), (0.4, _RAISED), (0.55, _STRIKE), (0.66, _RECOIL), (1.0, _READY)])
    for tag in ("L", "R"):
        solve_leg(b, ch, tag)
    return ch


_REST = {"upper_arm.L.abduct": -28, "upper_arm.R.abduct": -28, "forearm.L.bend": 14, "forearm.R.bend": 14}
_CROUCH = {"pelvis.z": -0.10, "spine.pitch": 14, "chest.pitch": 6, "head.pitch": 6, "upper_arm.L.swing": -25,
           "upper_arm.R.swing": -25, "upper_arm.L.abduct": -36, "upper_arm.R.abduct": -36, "forearm.L.bend": 25,
           "forearm.R.bend": 25}
_JUMP = {"pelvis.z": 0.13, "spine.pitch": -6, "chest.pitch": -12, "head.pitch": -14, "upper_arm.L.abduct": 128,
         "upper_arm.R.abduct": 128, "upper_arm.L.swing": 12, "upper_arm.R.swing": 12, "forearm.L.bend": 12,
         "forearm.R.bend": 12}
_LAND = {"pelvis.z": -0.05, "spine.pitch": 4, "chest.pitch": -8, "head.pitch": -8, "upper_arm.L.abduct": 118,
         "upper_arm.R.abduct": 118, "upper_arm.L.swing": 8, "upper_arm.R.swing": 8, "forearm.L.bend": 20,
         "forearm.R.bend": 20}
_PUMP = {"pelvis.z": -0.02, "chest.pitch": -6, "head.pitch": -6, "upper_arm.L.abduct": 95, "upper_arm.R.abduct": 95,
         "upper_arm.L.swing": 20, "upper_arm.R.swing": 20, "forearm.L.bend": 55, "forearm.R.bend": 55}


def celebrate(b: Body, t: float) -> dict[str, float]:
    """Crouch → jump with the arms thrown up and the chest back → land → pump → rest."""
    ch = _keys(t, [(0.0, _REST), (0.18, _CROUCH), (0.36, _JUMP), (0.56, _LAND), (0.78, _PUMP), (1.0, _REST)])
    for tag in ("L", "R"):
        solve_leg(b, ch, tag)
    return ch


CLIP_FUNCS: dict[str, Callable[[Body, float], dict[str, float]]] = {
    "idle": idle, "walk": walk, "talk": talk, "work": work, "celebrate": celebrate}


def pose(clip: str, b: Body, frame: int) -> dict[str, float]:
    """Channels of `clip` at `frame` (0 … CLIPS[clip]); the last frame equals the first."""
    return CLIP_FUNCS[clip](b, (frame % CLIPS[clip]) / CLIPS[clip])
