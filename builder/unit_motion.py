"""Shared rigid-part clips and scorpion kinematics, authored in Blender metres/Z-up."""

import math

SCORPION_CLIPS = {
    "idle": {"frames": 48, "loop": True},
    "walk": {"frames": 24, "loop": True},
    "attack_melee": {"frames": 30, "loop": False, "events": [{"seconds": .625, "name": "melee_contact"}]},
    "attack_ranged": {"frames": 36, "loop": False, "events": [{"seconds": .75, "name": "venom_release", "marker": "sting_venom_muzzle"}]},
    "hit": {"frames": 12, "loop": False},
    "death": {"frames": 36, "loop": False},
}
ENGINEER_CLIPS = {"idle": {"frames": 48, "loop": True}, "walk": {"frames": 96, "loop": True},
                  "build": {"frames": 96, "loop": True}}
HIP_Y = (-.5, -.25, .25, .5)
SPLAY = (-.1875, -.0625, .0625, .1875)
TAIL_ANGLES = (-50., 20., 45., 45.)
LEG_LENGTHS = (.5, .625)


def smooth(value):
    value = min(1., max(0., value))
    return value * value * (3 - 2 * value)


def pulse(phase):
    return math.sin(math.pi * phase) ** 4


def body_pose(clip, phase):
    dz = rx = ry = dead = 0.
    if clip == "idle":
        dz = .015 * math.sin(math.tau * phase)
    elif clip == "walk":
        dz = .015 * math.sin(2 * math.tau * phase)
    elif clip == "attack_melee":
        rx = math.radians(-6) * pulse(phase)
    elif clip == "attack_ranged":
        rx = math.radians(-3) * pulse(phase)
    elif clip == "hit":
        ry = math.radians(8) * math.sin(math.pi * phase)
    elif clip == "death":
        dead = smooth(phase / .7)
        dz, ry = -.1875 * dead, math.radians(8) * dead
    return {"dz": dz, "rx": rx, "ry": ry, "dead": dead}


def rotate(point, rx, ry, inverse=False):
    x, y, z = point
    if inverse:
        x, z = x * math.cos(ry) - z * math.sin(ry), x * math.sin(ry) + z * math.cos(ry)
        y, z = y * math.cos(rx) + z * math.sin(rx), -y * math.sin(rx) + z * math.cos(rx)
    else:
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    return (x, y, z)


def foot_target(clip, phase, side, index):
    """World-space foot centre. Stance stays grounded; alternate sets lift during swing."""
    stride = lift = 0.
    if clip == "walk":
        cycle = (phase + (index % 2) * .5 + (0 if side < 0 else .5)) % 1
        if cycle < .6:
            stride = -.125 + .25 * cycle / .6
        else:
            u = (cycle - .6) / .4
            stride = .125 - .25 * smooth(u)
            lift = .125 * math.sin(math.pi * u)
    dead = body_pose(clip, phase)["dead"]
    return (side * (1.125 - .1875 * dead), HIP_Y[index] + SPLAY[index] + stride, .0625 + lift)


def leg_points(clip, phase, side, index):
    """Two-link IK compensates the parent's bob/roll; ankle soles never follow the belly into the floor."""
    body = body_pose(clip, phase)
    foot = foot_target(clip, phase, side, index)
    local = rotate((foot[0], foot[1], foot[2] - .5 - body["dz"]), body["rx"], body["ry"], inverse=True)
    foot = (local[0] - side * .5, local[1] - HIP_Y[index], local[2] + .5)
    hip = (0., 0., .5)
    delta = tuple(foot[i] - hip[i] for i in range(3))
    distance = math.sqrt(sum(x * x for x in delta))
    upper, lower = LEG_LENGTHS
    if not abs(upper - lower) < distance < upper + lower:
        raise ValueError("leg target outside IK reach")
    direction = tuple(x / distance for x in delta)
    along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
    height = math.sqrt(max(0, upper * upper - along * along))
    preferred = (float(side), 0., 1.)
    dot = sum(preferred[i] * direction[i] for i in range(3))
    bend = tuple(preferred[i] - dot * direction[i] for i in range(3))
    norm = math.sqrt(sum(x * x for x in bend))
    knee = tuple(hip[i] + along * direction[i] + height * bend[i] / norm for i in range(3))
    return hip, knee, foot


def tail_angle(clip, phase, index):
    angle = TAIL_ANGLES[index]
    if clip == "idle":
        angle += 2 * math.sin(math.tau * phase) * (index + 1) / 4
    elif clip == "walk":
        angle += 3 * math.sin(math.tau * phase) * (index + 1) / 4
    elif clip == "attack_ranged":
        angle += (-8, -12, 15, 35)[index] * pulse(phase)
    elif clip == "attack_melee":
        angle += (0, 0, 4, -8)[index] * pulse(phase)
    elif clip == "hit":
        angle += (0, -5, 6, -8)[index] * math.sin(math.pi * phase)
    elif clip == "death":
        target = (-100, 65, 100, 70)[index]
        angle += (target - angle) * body_pose(clip, phase)["dead"]
    return math.radians(angle)


def bake_clips(objects, clips, pose):
    """One complete TRS action per rigid object/clip; shared NLA names merge in glTF.

    pose(clip, phase) assigns transforms. All axes are baked in all clips, so
    switching away from death restores the whole articulated hierarchy.
    """
    import bpy
    import voxlib as vx
    objects = list(objects)
    for obj in objects:
        if obj.rotation_mode != "QUATERNION":
            obj.rotation_quaternion = obj.rotation_euler.to_quaternion()
        obj.rotation_mode = "QUATERNION"
        obj.animation_data_create()
    rest = [(o.location.copy(), o.rotation_quaternion.copy(), o.scale.copy()) for o in objects]
    for name, spec in clips.items():
        for obj in objects:
            obj.animation_data.action = bpy.data.actions.new(f"{obj.name}_{name}")
        for frame in range(spec["frames"] + 1):
            pose(name, frame / spec["frames"])
            for obj in objects:
                for prop in ("location", "rotation_quaternion", "scale"):
                    obj.keyframe_insert(prop, frame=frame)
        for obj in objects:
            action = obj.animation_data.action
            vx._set_interpolation(action, "LINEAR")
            action["unit_clip"] = True
            action["clip_loop"] = spec["loop"]
            import json
            action["clip_events"] = json.dumps(spec.get("events", []))
            track = obj.animation_data.nla_tracks.new()
            track.name = name
            strip = track.strips.new(name, 0, action)
            strip.extrapolation = "NOTHING"
            obj.animation_data.action = None
    for obj, (loc, quat, scale) in zip(objects, rest):
        obj.location, obj.rotation_quaternion, obj.scale = loc, quat, scale


def contract(root, clips):
    import json
    root["animation_contract"] = json.dumps(clips)
