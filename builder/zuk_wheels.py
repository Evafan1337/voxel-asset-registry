"""Reusable Zuk wheel geometry and its inspection-loop running gear.

Pure kinematics use Blender coordinates (X axle, Z up, front -Y); Blender
imports stay inside render functions. Tire, rim and hub have separate meshes.
The loop demonstrates steering and independent suspension travel, rather than
simulating vehicle translation or a road-contact solver.
When changing shared geometry, increment both zk_wheel and zk_axle generator
versions so Registry invalidates their cached geometry together.
"""

from __future__ import annotations

import math
from typing import Any

try:
    from . import zuklib as zk
    from .vehicle_finish import color
except ImportError:
    import zuklib as zk
    from vehicle_finish import color

R, WIDTH, TRACK_HALF = zk.WHEEL_R, zk.WHEEL_WIDTH, zk.WHEEL_X
D = .0625
SUSPENSION_TOP = zk.SUSPENSION_TOP
SIDES = ((-1, "left"), (1, "right"))


def pose(t: float, side: int, params: dict[str, Any]) -> dict[str, float]:
    """One shared source for wheel pivots, rods, tests and baked animation."""
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    bump = float(params.get("bump", D)) * math.sin(math.pi * t * (1 if side < 0 else 2)) ** 2
    steering = (math.radians(float(params.get("steer_deg", 20))) * math.sin(math.tau * t)
                if params.get("steering", True) else 0.)
    return {"bump": bump, "steering": steering, "spin": math.tau * int(params.get("turns", 2)) * t}


def projected_half_extents(angle: float, params: dict[str, Any] | None = None) -> tuple[float, float]:
    """Conservative exact cylinder footprint, also valid for the 12-sided tire."""
    c, s = abs(math.cos(angle)), abs(math.sin(angle))
    width = zk.layout(params).wheel_width
    return width / 2 * c + R * s, width / 2 * s + R * c


def wheel_bounds(t: float, side: int, params: dict[str, Any]):
    state = pose(t, side, params)
    dx, dy = projected_half_extents(state["steering"], params)
    x, z = side * zk.layout(params).wheel_x, R + state["bump"]
    return ((x - dx, -dy, z - R), (x + dx, dy, z + R))


def swept_bounds(params: dict[str, Any], frames: int = 96):
    """Entire wheel motion envelope sampled at every frame of the shared clip."""
    bounds = [wheel_bounds(i / frames, side, params) for i in range(frames + 1) for side, _ in SIDES]
    return (tuple(min(b[0][axis] for b in bounds) for axis in range(3)),
            tuple(max(b[1][axis] for b in bounds) for axis in range(3)))


def rod_endpoints(t: float, side: int, kind: str, params: dict[str, Any]):
    """Fixed frame end and wheel-side end; independent arms remain connected."""
    profile = zk.layout(params)
    hub = (side * profile.wheel_x, 0., R + pose(t, side, params)["bump"])
    starts = {"shaft": (0., 0., R),
              "damper": (side * profile.suspension_x, 0., SUSPENSION_TOP),
              "control_arm": (side * profile.rail_inner, 0., .5)}
    if kind not in starts:
        raise ValueError(f"unknown suspension rod: {kind}")
    return starts[kind], hub


def rod_pose(t: float, side: int, kind: str, params: dict[str, Any]):
    start, end = rod_endpoints(t, side, kind, params)
    delta = tuple(b - a for a, b in zip(start, end))
    return {"center": tuple((a + b) / 2 for a, b in zip(start, end)),
            "length": math.dist(start, end), "angle": math.atan2(delta[0], delta[2])}


def wheel_parts(stage: int, part: str = "all") -> tuple[str, ...]:
    if stage not in (1, 2, 3) or part not in ("all", "tire", "rim"):
        raise ValueError("wheel stage must be 1..3 and part all/tire/rim")
    if part == "rim":
        return ("rim", "hub")
    if stage < 3 or part == "tire":
        return ("tire",)
    return ("tire", "rim", "hub")


def render_wheel(params: dict[str, Any], *, parent=None, location=(0., 0., R),
                 name="wheel", semantic_parts: bool = False):
    """One wheel kit reused by standalone recipes and both axle variants."""
    import voxlib as vx

    stage, part = int(params.get("stage", 3)), params.get("part", "all")
    width = zk.layout(params).wheel_width
    wheel_parts(stage, part)
    root = vx.empty(name, location=location, parent=parent)
    stage_gray = stage < 3 or not params.get("finish", True)
    tire_color = "steel_dark" if stage_gray else "rubber"
    rim_color = "paint_gray" if stage_gray else color(params, "wheel", "metal_steel")
    hub_color = "steel_dark" if stage_gray else color(params, "bare_metal", "metal_dark")

    def output(mesh, suffix):
        label = {"tire": "wheels", "rim": "rims", "hub": "hubs"}[suffix] if semantic_parts else "wheel"
        return mesh.to_object(f"{name}_{suffix}", parent=root, semantic_part=label)

    if part != "rim":
        mesh = vx.MeshBuilder()
        if stage == 1:
            mesh.box((-width / 2, -R, -R), (width / 2, R, R), "paint_gray")
        elif stage == 2:
            mesh.prism(R, -width / 2, width / 2, tire_color, sides=12, axis="X")
        else:
            mesh.ring(.21875, R, -width / 2, width / 2, tire_color, sides=12, axis="X")
        output(mesh, "tire")
    if part == "rim" or (stage == 3 and part == "all"):
        mesh = vx.MeshBuilder()
        mesh.ring(D, .21875, -width / 2 + D / 2, width / 2 - D / 2,
                  rim_color, sides=12, axis="X")
        output(mesh, "rim")
        mesh = vx.MeshBuilder()
        mesh.prism(D, -width / 2 + D / 2, width / 2 - D / 2, hub_color, sides=8, axis="X")
        for side, _ in SIDES:
            a, b = sorted((side * (width / 2 - D / 2), side * width / 2))
            mesh.prism(1.5 * D, a, b, hub_color, sides=8, axis="X")
        output(mesh, "hub")
    return root


def _render_rod(root, name, side, kind, params, animate):
    import voxlib as vx

    mesh = vx.MeshBuilder()
    metal = color(params, "bare_metal", "metal_dark") if params.get("finish", True) else "steel_dark"
    mesh.box((-D / 2, -D / 2, -.5), (D / 2, D / 2, .5), metal)
    initial = rod_pose(0., side, kind, params)
    obj = mesh.to_object(name, parent=root, location=initial["center"],
                         semantic_part="axle" if kind == "shaft" else "suspension")
    obj.rotation_euler[1], obj.scale[2] = initial["angle"], initial["length"]
    if animate:
        for axis in (0, 2):
            vx.periodic_animation(obj, "location", axis,
                                  lambda t, axis=axis: rod_pose(t, side, kind, params)["center"][axis])
        vx.periodic_animation(obj, "rotation_euler", 1, lambda t: rod_pose(t, side, kind, params)["angle"])
        vx.periodic_animation(obj, "scale", 2, lambda t: rod_pose(t, side, kind, params)["length"])
    return obj


def build_axle(params: dict[str, Any]):
    import voxlib as vx

    stage = int(params.get("stage", 3))
    profile = zk.layout(params)
    animate = stage == 3 and vx.level() >= 3 and params.get("animate", True)
    root = vx.empty("zk_axle")
    root["inspection_motion"] = "independent positive bump; parallel front steering; wheel spin"
    root["wheel_radius"], root["wheel_width"], root["track"] = R, profile.wheel_width, 2 * profile.wheel_x
    root["wheel_fit"] = params.get("wheel_fit", "legacy")
    root["steering_limit_degrees"] = params.get("steer_deg", 20) if params.get("steering", True) else 0.
    root["suspension_travel"] = params.get("bump", D)
    metal = color(params, "bare_metal", "metal_dark") if stage == 3 and params.get("finish", True) else "steel_dark"

    fixed = vx.MeshBuilder()
    if stage < 3:
        fixed.box((-profile.wheel_x, -D / 2, R - D / 2), (profile.wheel_x, D / 2, R + D / 2), metal)
    else:
        fixed.box((-D, -D, R - D), (D, D, R + D), metal)
    fixed.to_object("axle_center", parent=root, semantic_part="axle")

    for side, label in SIDES:
        mount = vx.MeshBuilder()
        mount.box((side * profile.suspension_x - D, -D, R),
                  (side * profile.suspension_x + D, D, SUSPENSION_TOP), metal)
        mount.to_object(f"suspension_mount_{label}", parent=root, semantic_part="suspension")
        vx.socket(f"suspension_{label}", (side * .625, 0., SUSPENSION_TOP), parent=root, type="generic")
        vx.socket(f"suspension_inset_{label}", (side * .375, 0., SUSPENSION_TOP), parent=root, type="generic")
        if stage < 3:
            render_wheel(params, parent=root, location=(side * profile.wheel_x, 0., R),
                         name=f"wheel_{label}", semantic_parts=True)
            continue
        bump = vx.empty(f"suspension_{label}", location=(side * profile.wheel_x, 0., R), parent=root)
        steer = vx.empty(f"steering_{label}", parent=bump)
        spin = vx.empty(f"spin_{label}", parent=steer)
        knuckle = vx.MeshBuilder()
        knuckle.box((-D, -D, -D), (D, D, D), metal)
        knuckle.to_object(f"knuckle_{label}", parent=bump, semantic_part="steering")
        render_wheel(params, parent=spin, location=(0., 0., 0.), name=f"wheel_{label}", semantic_parts=True)
        for kind in ("shaft", "damper", "control_arm"):
            _render_rod(root, f"{kind}_{label}", side, kind, params, animate)
        if animate:
            vx.periodic_animation(bump, "location", 2, lambda t, side=side: R + pose(t, side, params)["bump"])
            if params.get("steering", True):
                vx.periodic_animation(steer, "rotation_euler", 2,
                                      lambda t, side=side: pose(t, side, params)["steering"])
            vx.spin_animation(spin, axis=0, turns=int(params.get("turns", 2)))
    return root


def build_wheel(params: dict[str, Any]):
    import voxlib as vx

    root = vx.empty("zk_wheel")
    spin = vx.empty("wheel_spin", location=(0., 0., R), parent=root)
    render_wheel(params, parent=spin, location=(0., 0., 0.))
    if int(params.get("stage", 3)) == 3 and vx.level() >= 3 and params.get("animate", True):
        vx.spin_animation(spin, axis=0, turns=int(params.get("turns", 2)))
    return root
