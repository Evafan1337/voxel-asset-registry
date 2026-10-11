"""Read-only environment checks and the explicit public starter manifest contract."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from .config import ROOT, Config

STARTER_MANIFEST = ROOT / "release" / "starter-packs.yaml"
REFERENCE = re.compile(r"^(components|assets|materials|characters)/[A-Za-z0-9_-]+/v[0-9]{3,}$")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    required: bool
    detail: str


def node_supported(version: tuple[int, int, int]) -> bool:
    """The Node engines range in the frontend lockfile, not a generic '20+'."""
    major, minor, _patch = version
    return major == 20 and minor >= 19 or major == 22 and minor >= 12 or major > 22


def _probe(binary: str, pattern: str) -> tuple[tuple[int, int, int] | None, str]:
    if not binary or not shutil.which(binary):
        return None, "executable not found"
    try:
        process = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"version check failed: {type(exc).__name__}"
    output = (process.stdout + process.stderr).strip()
    match = re.search(pattern, output)
    if process.returncode != 0 or match is None:
        return None, f"version check failed (exit {process.returncode})"
    parts = [int(part or 0) for part in match.groups()]
    version = tuple((parts + [0, 0, 0])[:3])
    return version, ".".join(str(part) for part in version)


def find_godot(cfg: Config) -> str | None:
    if cfg.godot_bin:
        return cfg.godot_bin
    return shutil.which("godot") or shutil.which("godot4")


def _writable_destination(path: Path) -> bool:
    while not path.exists() and path.parent != path:
        path = path.parent
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)


def environment_checks(cfg: Config, *, frontend: bool = True,
                       require_blender: bool = False, skip_blender: bool = False,
                       registry: bool = True) -> list[Check]:
    checks = [
        Check("python", sys.version_info >= (3, 11), True,
              f"{platform.python_version()}; requires 3.11+, verified with 3.12"),
        Check("platform", platform.system() == "Linux", False,
              f"{platform.system()}; Linux source setup is verified, other systems are not verified"),
    ]
    if frontend:
        node, detail = _probe("node", r"v?(\d+)\.(\d+)\.(\d+)")
        checks.append(Check("node", node is not None and node_supported(node), True,
                            f"{detail}; requires 20.19+ in Node 20 or 22.12+"))
        npm, detail = _probe("npm", r"(\d+)\.(\d+)\.(\d+)")
        checks.append(Check("npm", npm is not None, True, detail))
    if not skip_blender:
        blender, detail = _probe(cfg.blender_bin, r"Blender\s+(\d+)\.(\d+)(?:\.(\d+))?")
        checks.append(Check("blender", blender is not None and blender >= (5, 1, 0), require_blender,
                            f"{detail}; requires 5.1+ for model builds"))
    godot, detail = _probe(find_godot(cfg) or "", r"(\d+)\.(\d+)(?:\.(\d+))?")
    checks.append(Check("godot", godot is not None and godot[0] == 4, False,
                        f"{detail}; Godot 4 is optional for export checks"))
    if registry:
        checks.append(Check("registry", (cfg.registry_dir / "palette.yaml").is_file(), True,
                            "palette found" if (cfg.registry_dir / "palette.yaml").is_file()
                            else "missing palette; run python -m registry init"))
        for name, path in (("build destination", cfg.build_dir), ("index destination", cfg.db_path.parent)):
            checks.append(Check(name, _writable_destination(path), True,
                                "writable" if _writable_destination(path) else "not writable"))
    return checks


def checks_ok(checks: list[Check]) -> bool:
    return all(check.ok for check in checks if check.required)


def render_checks(checks: list[Check], *, as_json: bool = False) -> None:
    if as_json:
        import json
        print(json.dumps({"ok": checks_ok(checks), "checks": [asdict(check) for check in checks]}, indent=2))
        return
    for check in checks:
        state = "OK" if check.ok else "FAIL" if check.required else "OPTIONAL"
        print(f"{state:<8} {check.name}: {check.detail}")


def starter_targets(path: Path = STARTER_MANIFEST, packs: list[str] | None = None) -> list[str]:
    """Validate and select explicit build refs, never an implicit full-registry build."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read starter manifest: {path.name}") from exc
    if not isinstance(data, dict) or data.get("schema") != "public-alpha/v1":
        raise ValueError("starter manifest schema must be public-alpha/v1")

    def refs(value: object, label: str) -> list[str]:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{label} must be a non-empty list of references")
        if any(not isinstance(ref, str) or not REFERENCE.fullmatch(ref) for ref in value):
            raise ValueError(f"{label} contains an invalid reference")
        if len(value) != len(set(value)):
            raise ValueError(f"{label} contains duplicate references")
        return value

    demo = refs(data.get("demo_refs"), "demo_refs")
    entries = data.get("packs")
    if not isinstance(entries, list) or not entries:
        raise ValueError("packs must be a non-empty list")
    available: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise ValueError("every pack needs a non-empty id")
        name = entry["id"]
        if name in available:
            raise ValueError(f"duplicate pack id: {name}")
        available[name] = refs(entry.get("refs"), f"pack {name} refs")
    if not packs:
        return demo
    unknown = sorted(set(packs) - available.keys())
    if unknown:
        raise ValueError(f"unknown pack(s): {', '.join(unknown)}; available: {', '.join(available)}")
    return list(dict.fromkeys(ref for name in packs for ref in available[name]))
