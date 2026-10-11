"""Package built public starter models, without local recipes, logs or source paths.

Run only after the public checkout's declared starter models have been built:
    python tools/public_models.py --source var/public-alpha/install-check

The output is a deterministic release attachment, separate from the source tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import struct
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import Config
from backend.planner import Planner
from backend.resolve import RecipeError
from backend.store import Store
from builder.projection_views import PREVIEW_FILES
from tools.public_release import (
    ExportError, PRIVACY_RULES, image_metadata_text, load_manifest, parse_ref, published_refs,
)

SCHEMA = "public-starter-models/v1"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]*")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _private_text(text: str, label: str) -> None:
    for category, pattern in PRIVACY_RULES:
        if pattern.search(text):
            raise ExportError(f"{label}: privacy gate failed ({category})")


def _read(path: Path, root: Path) -> bytes:
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ExportError("artifact symlinks and external files are not allowed")
    relative = path.relative_to(root)
    if any(root.joinpath(*relative.parts[:i]).is_symlink() for i in range(1, len(relative.parts))):
        raise ExportError("artifact directory symlinks are not allowed")
    if not path.is_file():
        raise ExportError(f"required public artifact is missing: {relative.as_posix()}")
    return path.read_bytes()


def validate_glb(data: bytes) -> None:
    """Validate the container, self-contained resources and readable JSON metadata.

    Mesh float bytes are not text. Embedded PNG/WebP image metadata is inspected
    separately, using the same reader as the public source exporter.
    """
    if len(data) < 20:
        raise ExportError("invalid GLB header")
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise ExportError("invalid GLB header or declared length")
    chunks: list[tuple[int, bytes]] = []
    offset = 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise ExportError("truncated GLB chunk")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if size % 4 or offset + size > len(data):
            raise ExportError("invalid GLB chunk size")
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    if not chunks or chunks[0][0] != 0x4E4F534A or len(chunks) > 2:
        raise ExportError("GLB must contain one JSON chunk and an optional BIN chunk")
    if len(chunks) == 2 and chunks[1][0] != 0x004E4942:
        raise ExportError("unsupported GLB chunk")
    try:
        document = json.loads(chunks[0][1].decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ExportError("invalid GLB JSON") from exc
    if not isinstance(document, dict) or not isinstance(document.get("asset"), dict) \
            or document["asset"].get("version") != "2.0":
        raise ExportError("GLB must declare glTF 2.0")
    if not isinstance(document.get("meshes"), list) or not document["meshes"]:
        raise ExportError("GLB must contain model meshes")
    try:
        text = json.dumps(document, ensure_ascii=False, allow_nan=False)
    except ValueError as exc:
        raise ExportError("GLB JSON contains non-finite numbers") from exc
    _private_text(text, "GLB JSON")

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            # These exports use embedded bufferViews. No external resources, including
            # relative filenames, may silently escape the single-file model archive.
            if "uri" in value:
                raise ExportError("GLB resource URIs are not allowed; use embedded bufferViews")
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            # Inspect decoded strings too: JSON escaping doubles backslashes in
            # Windows paths and can hide them from a scan of serialized JSON.
            _private_text(value, "GLB JSON string")

    inspect(document)
    binary = chunks[1][1] if len(chunks) == 2 else b""
    views = document.get("bufferViews", [])
    images = document.get("images", [])
    if not isinstance(views, list) or not isinstance(images, list):
        raise ExportError("invalid GLB resource tables")
    for image in images:
        if not isinstance(image, dict) or type(image.get("bufferView")) is not int:
            raise ExportError("GLB images must use embedded bufferViews")
        index = image["bufferView"]
        if index < 0 or index >= len(views) or not isinstance(views[index], dict):
            raise ExportError("invalid GLB image bufferView")
        view = views[index]
        start, size = view.get("byteOffset", 0), view.get("byteLength")
        if view.get("buffer") != 0 or type(start) is not int or type(size) is not int \
                or start < 0 or size < 0 or start + size > len(binary):
            raise ExportError("invalid GLB embedded image bounds")
        _private_text(image_metadata_text(binary[start:start + size]), "GLB embedded image")


def _vec3(value: Any, label: str, *, positive: bool = False) -> list[float]:
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number)
        or positive and number <= 0 for number in value
    ):
        raise ExportError(f"invalid public model {label}")
    return value


def model_metadata(report: Any, ref: str, digest: str) -> dict[str, Any]:
    kind, entity_id, variant = parse_ref(ref)
    if not isinstance(report, dict) or report.get("status") != "ok":
        raise ExportError(f"public model has no successful report: {ref}")
    # Multiple variant IDs can deliberately share one recipe hash and cached report.
    # Its original build variant may differ; the resolved geometry identity must match.
    if any(report.get(key) != expected for key, expected in (
        ("hash", digest), ("kind", kind), ("id", entity_id)
    )):
        raise ExportError(f"public build report does not match its recipe: {ref}")
    raw_checks = report.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise ExportError(f"public model report has no checks: {ref}")
    checks = []
    for check in raw_checks:
        if not isinstance(check, dict) or not isinstance(check.get("name"), str) \
                or not NAME.fullmatch(check["name"]) or check.get("ok") is not True:
            raise ExportError(f"public model checks are not all successful: {ref}")
        checks.append({"name": check["name"], "ok": True})
    stats = report.get("stats")
    if not isinstance(stats, dict):
        raise ExportError(f"public model report has no geometry stats: {ref}")
    safe_stats: dict[str, Any] = {"bbox_m": _vec3(stats.get("bbox_m"), "bbox", positive=True)}
    for key in ("vertices", "faces", "triangles", "objects"):
        if key in stats:
            if type(stats[key]) is not int or stats[key] < 0:
                raise ExportError(f"invalid public model count: {key}")
            safe_stats[key] = stats[key]
    sockets = stats.get("sockets", [])
    if not isinstance(sockets, list):
        raise ExportError("invalid public model sockets")
    safe_stats["sockets"] = []
    for socket in sockets:
        if not isinstance(socket, dict) or not isinstance(socket.get("name"), str) \
                or not NAME.fullmatch(socket["name"]):
            raise ExportError("invalid public model socket name")
        safe_stats["sockets"].append({"name": socket["name"], "position": _vec3(socket.get("position"), "socket position")})
    metadata = {"schema": "public-model/v1", "ref": ref, "hash": digest, "status": "ok",
                "license": "CC0-1.0", "units": "meters", "axes": "gltf_y_up",
                "checks": checks, "stats": safe_stats}
    _private_text(_json_bytes(metadata).decode("utf-8"), "model metadata")
    return metadata


def _output_path(path: Path) -> Path:
    path = path.absolute()
    allowed = PROJECT_ROOT / "var/public-alpha"
    if path.suffix != ".zip" or not path.resolve().is_relative_to(allowed.resolve()):
        raise ExportError("model archive must be a ZIP inside var/public-alpha")
    if path.is_symlink():
        raise ExportError("model archive cannot be a symlink")
    for parent in (path.parent, *path.parents):
        if parent == PROJECT_ROOT:
            break
        if parent.is_symlink():
            raise ExportError("model archive directory symlinks are not allowed")
    if path.exists():
        try:
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo("index.json")
                record = json.loads(archive.read(info)) if info.file_size <= 1_000_000 else None
                if not isinstance(record, dict) or record.get("schema") != SCHEMA:
                    raise ValueError("invalid archive marker")
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            raise ExportError("refusing to replace an archive without a starter-model marker") from exc
    return path


def export_models(source: Path, out: Path) -> dict[str, Any]:
    source = source.resolve()
    out = _output_path(out)
    if out.resolve().is_relative_to(source):
        raise ExportError("model archive must be outside the source checkout")
    manifest_path = source / "release/starter-packs.yaml"
    manifest_bytes = _read(manifest_path, source)
    manifest = load_manifest(manifest_path)
    refs = [ref for ref in published_refs(manifest) if parse_ref(ref)[0] != "materials"]
    if not refs:
        raise ExportError("starter manifest contains no model roots")
    planner = Planner(Store(source / "registry"), Config(registry_dir=source / "registry", build_dir=source / "build"))
    entries: dict[str, bytes] = {}
    models = []
    for ref in refs:
        kind, entity_id, variant = parse_ref(ref)
        try:
            digest = planner.resolve(kind, entity_id, variant).hash  # type: ignore[arg-type]
        except (RecipeError, FileNotFoundError) as exc:
            raise ExportError(f"cannot resolve public model recipe: {ref}") from exc
        folder = source / "build" / digest
        try:
            report = json.loads(_read(folder / "report.json", source))
        except (ValueError, UnicodeError) as exc:
            raise ExportError(f"invalid public build report: {ref}") from exc
        metadata = model_metadata(report, ref, digest)
        prefix = f"models/{kind}/{entity_id}/{variant}"
        model = _read(folder / "model.glb", source)
        validate_glb(model)
        entries[f"{prefix}/model.glb"] = model
        for name in PREVIEW_FILES:
            preview = _read(folder / name, source)
            if not preview.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ExportError(f"invalid projection PNG: {ref}/{name}")
            _private_text(image_metadata_text(preview), "projection image metadata")
            entries[f"{prefix}/{name}"] = preview
        entries[f"{prefix}/metadata.json"] = _json_bytes(metadata)
        models.append({"ref": ref, "hash": digest, "path": f"{prefix}/model.glb",
                       "previews": [f"{prefix}/{name}" for name in PREVIEW_FILES],
                       "pack_ids": [pack["id"] for pack in manifest["packs"] if ref in pack["refs"]]})
    for name in ("LICENSE-ASSETS", "NOTICE"):
        value = _read(source / name, source)
        try:
            _private_text(value.decode("utf-8"), name)
        except UnicodeError as exc:
            raise ExportError(f"{name} must be UTF-8 text") from exc
        entries[name] = value
    files = [{"path": name, "size": len(value), "sha256": hashlib.sha256(value).hexdigest()}
             for name, value in sorted(entries.items())]
    entries["index.json"] = _json_bytes({"schema": SCHEMA, "license": "CC0-1.0", "models": models,
                                          "starter_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                                          "files": files, "index_hash_included": False})
    _private_text(entries["index.json"].decode("utf-8"), "archive index")
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".starter-models-", suffix=".zip", dir=out.parent, delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, value in sorted(entries.items()):
                item = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                item.create_system = 3
                item.external_attr = (stat.S_IFREG | 0o644) << 16
                item.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(item, value, compresslevel=9)
        temporary.chmod(0o644)
        temporary.replace(out)
        return {"schema": SCHEMA, "models": len(models), "files": len(entries),
                "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "archive": out.name}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package built public starter models; never publish")
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "var/public-alpha/install-check")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "var/public-alpha/starter-models-alpha.zip")
    args = parser.parse_args(argv)
    try:
        print(json.dumps({"status": "ok", **export_models(args.source, args.out)}, sort_keys=True))
        return 0
    except (ExportError, RecipeError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"starter models export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
