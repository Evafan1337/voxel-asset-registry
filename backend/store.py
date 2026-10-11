"""Filesystem registry: the source of truth for entities and variants."""

from __future__ import annotations

import math
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from . import frontmatter
from .models import KINDS, EntityDoc, Kind, Variant, variant_model, variant_to_yaml_dict
from .resolve import RecipeError, resolve_entity

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
_VID_RE = re.compile(r"^v(\d+)$")
MATERIAL_ROLES = ("body", "trim", "bare_metal", "track", "wheel", "glass", "lamp", "cargo", "canvas", "antenna",
                  "muzzle")


def check_id(value: str) -> str:
    if not _ID_RE.match(value):
        raise RecipeError(f"invalid id '{value}'")
    return value


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Palette:
    def __init__(self, voxel_size: float, colors: dict[str, str], surfaces: dict[str, str] | None = None,
                 surface_types: dict[str, dict[str, float]] | None = None):
        self.voxel_size = voxel_size
        self.colors = colors
        self.surfaces = surfaces or {}                # color → material class; the rest is paint
        self.surface_types = surface_types or {}      # class → metallic / roughness / emission

    def as_dict(self) -> dict[str, Any]:
        return {"voxel_size": self.voxel_size, "colors": self.colors, "surfaces": self.surfaces,
                "surface_types": self.surface_types}


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.write_lock = threading.RLock()

    # ------------------------------------------------------------------ paths
    def kind_dir(self, kind: Kind) -> Path:
        return self.root / kind

    def entity_dir(self, kind: Kind, entity_id: str) -> Path:
        return self.kind_dir(kind) / check_id(entity_id)

    def variant_path(self, kind: Kind, entity_id: str, vid: str) -> Path:
        return self.entity_dir(kind, entity_id) / "variants" / f"{check_id(vid)}.yaml"

    def source_path(self, kind: Kind, entity_id: str, name: str) -> Path:
        """Manual geometry file of a variant (`source: v004.blend`), stored beside its YAML."""
        if "/" in name or "\\" in name or name.startswith("."):
            raise RecipeError(f"bad source file name '{name}'")
        return self.entity_dir(kind, entity_id) / "variants" / name

    def generator_path(self, entity_id: str, kind: Kind = "components") -> Path:
        """components: generator.py (geometry); materials: blender.py (node material + outlines)."""
        name = "blender.py" if kind == "materials" else "generator.py"
        return self.entity_dir(kind, entity_id) / name

    def entity_file(self, kind: Kind, entity_id: str, name: str) -> Path:
        if "/" in name or name.startswith("."):
            raise RecipeError(f"bad file name '{name}'")
        return self.entity_dir(kind, entity_id) / name

    # ------------------------------------------------------------------ entities
    def entity_ids(self, kind: Kind) -> list[str]:
        base = self.kind_dir(kind)
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if (p / "_base.md").is_file())

    def has_entity(self, kind: Kind, entity_id: str) -> bool:
        return (self.entity_dir(kind, entity_id) / "_base.md").is_file()

    def read_base(self, kind: Kind, entity_id: str) -> tuple[dict[str, Any], str]:
        path = self.entity_dir(kind, entity_id) / "_base.md"
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            return frontmatter.parse(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, ValueError) as exc:
            raise RecipeError(f"{path.relative_to(self.root)}: {exc}") from exc

    def resolve(self, kind: Kind, entity_id: str) -> EntityDoc:
        """Resolved description. Parents are looked up in the same kind first, then the other one."""
        def load(eid: str) -> tuple[dict[str, Any], str]:
            for k in (kind, *[x for x in KINDS if x != kind]):
                if self.has_entity(k, eid):
                    return self.read_base(k, eid)
            raise FileNotFoundError(eid)
        return resolve_entity(kind, entity_id, load)

    # ------------------------------------------------------------------ variants
    def variants(self, kind: Kind, entity_id: str) -> tuple[dict[str, Variant], list[str]]:
        """All parseable variants plus a list of per-file errors."""
        folder = self.entity_dir(kind, entity_id) / "variants"
        model = variant_model(kind)
        found: dict[str, Variant] = {}
        errors: list[str] = []
        if not folder.is_dir():
            return found, errors
        for path in sorted(folder.glob("*.yaml")):
            rel = path.relative_to(self.root)
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                variant = model.model_validate(data)
            except (yaml.YAMLError, ValidationError) as exc:
                errors.append(f"{rel}: {exc}")
                continue
            if variant.id != path.stem:
                errors.append(f"{rel}: id '{variant.id}' does not match file name")
                continue
            found[variant.id] = variant
        return found, errors

    def variant(self, kind: Kind, entity_id: str, vid: str) -> Variant:
        path = self.variant_path(kind, entity_id, vid)
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return variant_model(kind).model_validate(data)
        except (yaml.YAMLError, ValidationError) as exc:
            raise RecipeError(f"{path.relative_to(self.root)}: {exc}") from exc

    def save_variant(self, kind: Kind, entity_id: str, variant: Variant) -> Path:
        with self.write_lock:
            path = self.variant_path(kind, entity_id, variant.id)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".yaml.tmp")
            tmp.write_text(frontmatter.dump_yaml(variant_to_yaml_dict(variant)), encoding="utf-8")
            tmp.replace(path)
            return path

    def create_asset(self, meta: dict[str, Any], description: str, variant: Variant) -> Path:
        """Create a new independent asset recipe atomically at the directory level."""
        with self.write_lock:
            return self._create_asset(meta, description, variant)

    def _create_asset(self, meta: dict[str, Any], description: str, variant: Variant) -> Path:
        entity_id = check_id(str(meta["id"]))
        folder = self.entity_dir("assets", entity_id)
        folder.parent.mkdir(parents=True, exist_ok=True)
        try:
            folder.mkdir()
        except FileExistsError as exc:
            raise RecipeError(f"assets/{entity_id} already exists") from exc
        try:
            body = f"---\n{frontmatter.dump_yaml(meta)}---\n"
            if description.strip():
                body += f"\n{description.strip()}\n"
            (folder / "_base.md").write_text(body, encoding="utf-8")
            self.save_variant("assets", entity_id, variant)
        except Exception:
            shutil.rmtree(folder)
            raise
        return folder

    def catalog_groups(self) -> list[dict[str, Any]]:
        """Presentation-only organization, stored away from build recipes."""
        path = self.root / "catalog_groups.yaml"
        if not path.is_file():
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise RecipeError(f"{path.name}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("groups", []), list):
            raise RecipeError(f"{path.name}: expected groups list")
        return data.get("groups", [])

    def save_catalog_groups(self, groups: list[dict[str, Any]]) -> Path:
        path = self.root / "catalog_groups.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".yaml.tmp")
        tmp.write_text(frontmatter.dump_yaml({"groups": groups}), encoding="utf-8")
        tmp.replace(path)
        return path

    def next_vid(self, kind: Kind, entity_id: str) -> str:
        folder = self.entity_dir(kind, entity_id) / "variants"
        numbers = [int(m.group(1)) for p in folder.glob("v*.yaml") if (m := _VID_RE.match(p.stem))]
        return f"v{max(numbers, default=0) + 1:03d}"

    # ------------------------------------------------------------------ palette
    def palette(self) -> Palette:
        path = self.root / "palette.yaml"
        if not path.is_file():
            raise RecipeError("registry/palette.yaml is missing (run `python -m registry init`)")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        colors = {str(k): str(v) for k, v in (data.get("colors") or {}).items()}
        bad = [k for k, v in colors.items() if not re.fullmatch(r"#[0-9a-fA-F]{6}", v)]
        if bad:
            raise RecipeError(f"palette colors must be #rrggbb: {bad}")
        types = {str(k): {str(p): float(x) for p, x in (v or {}).items()}
                 for k, v in (data.get("surface_types") or {}).items()}
        surfaces = {str(k): str(v) for k, v in (data.get("surfaces") or {}).items()}
        unknown = [k for k in surfaces if k not in colors] + [v for v in surfaces.values() if v not in types]
        if unknown or "paint" in types:
            raise RecipeError(f"palette surfaces: unknown colors or classes {unknown} ('paint' is implicit)")
        return Palette(float(data.get("voxel_size", 0.25)), colors, surfaces, types)

    def material_preset(self, name: str) -> dict[str, Any]:
        """Resolve one opt-in finish, including only its referenced colors and effective PBR values."""
        if not isinstance(name, str):
            raise RecipeError("material preset name must be a string")
        check_id(name)
        path = self.root / "material_presets.yaml"
        if not path.is_file():
            raise RecipeError(f"material preset '{name}': registry/material_presets.yaml is missing")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise RecipeError(f"{path.name}: {exc}") from exc
        presets = data.get("presets") if isinstance(data, dict) else None
        if not isinstance(presets, dict):
            raise RecipeError(f"{path.name}: expected presets mapping")
        if name not in presets:
            raise RecipeError(f"unknown material preset '{name}'")
        preset = presets[name]
        if not isinstance(preset, dict) or set(preset) - {"title", "description", "colors", "materials"}:
            raise RecipeError(f"material preset '{name}': expected title, colors and materials")
        colors = preset.get("colors")
        if not isinstance(colors, dict) or set(colors) != set(MATERIAL_ROLES):
            raise RecipeError(f"material preset '{name}': colors must define roles {', '.join(MATERIAL_ROLES)}")
        palette = self.palette()
        unknown = [str(color) for color in colors.values()
                   if not isinstance(color, str) or color not in palette.colors]
        if unknown:
            raise RecipeError(f"material preset '{name}': unknown palette colors {unknown}")
        overrides = preset.get("materials", {})
        if not isinstance(overrides, dict):
            raise RecipeError(f"material preset '{name}': materials must map palette colors to PBR properties")

        def properties(values: Any, color: str) -> dict[str, Any]:
            if not isinstance(values, dict) or set(values) - {"metallic", "roughness", "emission", "texture"}:
                raise RecipeError(f"material preset '{name}', {color}: expected metallic/roughness/emission/texture")
            result: dict[str, Any] = {"metallic": 0.0, "roughness": 0.85, "emission": 0.0}
            for key, value in values.items():
                if key == "texture":
                    from builder.metal_texture import settings
                    try:
                        if not isinstance(value, dict) or set(value) - {"style", "strength", "density", "seed"}:
                            raise ValueError("expected style/strength/density/seed")
                        result[key] = settings(**value)
                    except (TypeError, ValueError) as exc:
                        raise RecipeError(f"material preset '{name}', {color}: invalid texture: {exc}") from exc
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError, OverflowError):
                    number = float("nan")
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(number) or number < 0
                        or (key != "emission" and number > 1)):
                    raise RecipeError(f"material preset '{name}', {color}: invalid {key} value {value!r}")
                result[key] = number
            return result

        for color, values in overrides.items():
            if color not in palette.colors:
                raise RecipeError(f"material preset '{name}': unknown material color '{color}'")
            properties(values, color)
        materials = {}
        for color in sorted(set(colors.values())):
            surface = palette.surfaces.get(color)
            values = {**palette.surface_types.get(surface, {}), **overrides.get(color, {})}
            materials[color] = properties(values, color)
        return {"preset": name, "colors": dict(colors),
                "color_values": {color: palette.colors[color] for color in materials},
                "materials": materials}
