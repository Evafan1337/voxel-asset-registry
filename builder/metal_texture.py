"""Small deterministic pixel textures; no external image or Blender dependency."""

import math
import random

VERSION = 2
STYLES = ("none", "grain", "brushed", "hammered")
SIZE = 64


def settings(style="grain", strength=0.035, density=32.0, seed=13):
    if style not in STYLES:
        raise ValueError("unknown metal texture style")
    for name, value, low, high in (("strength", strength, 0, .15), ("density", density, 4, 128)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"invalid metal texture {name}")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 65535:
        raise ValueError("invalid metal texture seed")
    return {"style": style, "strength": float(strength), "density": float(density), "seed": seed, "version": VERSION}


def pixels(config, roughness=.25, metallic=.65):
    rng = random.Random(config["seed"])
    noise = [[rng.uniform(-1, 1) for _ in range(SIZE)] for _ in range(SIZE)]
    bands = [rng.uniform(-1, 1) for _ in range(SIZE)]
    dents = [[rng.uniform(-1, 1) for _ in range(SIZE // 4)] for _ in range(SIZE // 4)]
    albedo, orm = [], []
    for y in range(SIZE):
        for x in range(SIZE):
            value = noise[y][x]
            if config["style"] == "brushed":
                value = .8 * bands[y] + .2 * value
            elif config["style"] == "hammered":
                value = .75 * dents[y // 4][x // 4] + .25 * value
            if config["style"] == "none":
                value = 0.0
            shade = 1 if config["style"] == "none" else 1 - config["strength"] + config["strength"] * value
            albedo.extend((shade, shade, shade, 1))
            # Keep shiny metal coherent: roughness should not turn individual
            # pixels into harsh, flashing specular flecks.
            rough = max(.02, min(1, roughness + value * config["strength"] * .5))
            orm.extend((1, rough, metallic, 1))
    return albedo, orm
