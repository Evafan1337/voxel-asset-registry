"""Project configuration loaded from config.yaml."""

from __future__ import annotations

import os
import re
import stat
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator

ROOT = Path(__file__).resolve().parent.parent
BUILDER_SCRIPT = ROOT / "builder" / "build.py"
FRONTEND_DIST = ROOT / "frontend" / "dist"
SEED_DIR = ROOT / "backend" / "seed" / "registry"


class Limits(BaseModel):
    poly_limit_asset: int = 5000
    poly_limit_component: int = 3000
    poly_limit_character: int = 4000   # faces of a whole skinned character (body, face, hair, gear)
    bbox_tolerance: float = 0.02


class LegacySource(BaseModel):
    name: str
    label: str
    path: Path


class Legacy(BaseModel):
    """Read-only catalog of models made before the registry (see backend/legacy.py)."""

    parallel: int = 4
    sources: list[LegacySource] = Field(default_factory=list)


class Server(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


def _normalize_priority_tags(tags: list[str]) -> list[str]:
    normalized = [tag.strip() for tag in tags]
    if any(not tag for tag in normalized):
        raise ValueError("priority_tags cannot contain empty tags")
    if len(normalized) != len(set(normalized)):
        raise ValueError("priority_tags cannot contain duplicates")
    return normalized


class RegistrySettings(BaseModel):
    priority_tags: list[str]

    @field_validator("priority_tags")
    @classmethod
    def validate_priority_tags(cls, tags: list[str]) -> list[str]:
        return _normalize_priority_tags(tags)


class Config(BaseModel):
    _source_path: Path = PrivateAttr(
        default_factory=lambda: Path(os.environ.get("REGISTRY_CONFIG", ROOT / "config.yaml"))
    )

    blender_bin: str = "blender"
    godot_bin: str = ""                 # empty → auto-detect in PATH
    godot_vulkan_icd: str = ""           # optional software Vulkan ICD for xvfb
    registry_dir: Path = Path("registry")
    build_dir: Path = Path("build")
    db_path: Path = Path("var/index.sqlite")
    parallel_builds: int = 1
    build_timeout: int = 300
    preview_size: int = 512
    priority_tags: list[str] = Field(default_factory=list)
    limits: Limits = Limits()
    server: Server = Server()
    legacy: Legacy = Field(default_factory=Legacy)

    @field_validator("priority_tags")
    @classmethod
    def validate_priority_tags(cls, tags: list[str]) -> list[str]:
        return _normalize_priority_tags(tags)

    def model_post_init(self, _context: object) -> None:
        for name in ("registry_dir", "build_dir", "db_path"):
            value: Path = getattr(self, name)
            if not value.is_absolute():
                setattr(self, name, ROOT / value)
        for src in self.legacy.sources:
            if not src.path.is_absolute():
                src.path = (ROOT / src.path).resolve()


def _config_data(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if data is not None and not isinstance(data, dict):
        raise ValueError(f"configuration must be a YAML mapping: {path}")
    return data or {}


def _merge_config(base: dict, override: dict) -> dict:
    """Merge mapping values; lists such as legacy sources are replaced explicitly."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> Config:
    explicit = path is not None or bool(os.environ.get("REGISTRY_CONFIG"))
    path = path or Path(os.environ.get("REGISTRY_CONFIG") or ROOT / "config.yaml")
    if not explicit and not path.exists():
        path = ROOT / "config.example.yaml"
    data = _config_data(path)
    local = ROOT / "config.local.yaml"
    if not explicit and local.exists():
        data = _merge_config(data, _config_data(local))
        path = local
    cfg = Config.model_validate(data or {})
    cfg._source_path = path.resolve()
    return cfg


class _IndentedSafeDumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        return super().increase_indent(flow, False)


def render_priority_tags(source: str, tags: list[str]) -> str:
    """Replace the priority list without changing other project settings."""
    tags = RegistrySettings(priority_tags=tags).priority_tags
    data = yaml.safe_load(source) or {}
    if not isinstance(data, dict):
        raise ValueError("project config must be a YAML mapping")
    had_key = "priority_tags" in data
    data["priority_tags"] = tags

    block = yaml.dump({"priority_tags": tags}, Dumper=_IndentedSafeDumper,
                      allow_unicode=True, sort_keys=False)
    lines = source.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if re.match(r"^priority_tags\s*:", line)]
    if len(matches) == 1:
        start = matches[0]
        # Keep the explanation attached to the setting in the project's config.yaml.
        comment = re.match(r"^priority_tags\s*:\s*(?:\[[^\]]*\]\s*)?(#.*)$",
                           lines[start].rstrip("\r\n"))
        if comment:
            first_line, newline, rest = block.partition("\n")
            block = f"{first_line}  {comment.group(1)}{newline}{rest}"
        end = start + 1
        while end < len(lines) and (
            (lines[end].strip() and lines[end][0].isspace())
            or lines[end].startswith("- ")
        ):
            end += 1
        candidate = "".join([*lines[:start], block, *lines[end:]])
    elif not had_key and not matches:
        candidate = source.rstrip() + ("\n\n" if source.strip() else "") + block
    else:
        candidate = ""
    # Fallback handles unusual YAML syntax while keeping all other values and key order.
    try:
        valid_candidate = bool(candidate) and yaml.safe_load(candidate) == data
    except yaml.YAMLError:
        valid_candidate = False
    if not valid_candidate:
        candidate = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return candidate


def save_priority_tags(cfg: Config, tags: list[str]) -> None:
    """Persist only the priority list, preserving the rest of the YAML when possible."""
    path = cfg._source_path
    source = path.read_text(encoding="utf-8") if path.exists() else ""
    candidate = render_priority_tags(source, tags)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(candidate)
            tmp.flush()
            os.fsync(tmp.fileno())
        if path.exists():
            tmp_path.chmod(stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
