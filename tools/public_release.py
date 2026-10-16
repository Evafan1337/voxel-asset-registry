"""Export a curated public source tree without copying the private workspace.

Run from the project root with the project's Python environment:
    python tools/public_release.py

The exporter never reads Git history and never publishes. Existing output is
replaced only when it bears this exporter's marker. Privacy findings are reported
as relative paths and categories, without printing the matched personal data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import struct
import sys
import tempfile
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Verifying a clean checkout must not create unlisted bytecode in that checkout.
sys.dont_write_bytecode = True
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import frontmatter
from backend.cli import cmd_check
from backend.config import Config
from backend.models import KINDS
from backend.planner import AssetResolution, Planner
from backend.resolve import RecipeError
from backend.store import Store

SCHEMA = "public-alpha/v1"
CONTENT_MANIFEST = "release/content-manifest.json"
EXPORT_SCHEMA = "public-source-export/v1"
REF_RE = re.compile(r"^(components|assets|materials)/([a-z0-9][a-z0-9_-]*)/(v[0-9]+)$")
PRIVATE_DIRS = {".git", ".venv", ".aws", ".codex", ".agents", ".pytest_cache", "__pycache__", "node_modules", "dist"}
PRIVATE_SUFFIXES = {".blend", ".blend1", ".glb", ".gltf", ".npz", ".sqlite", ".log", ".zip"}
TEXT_SUFFIXES = {".py", ".sh", ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".html",
                 ".ts", ".css", ".js", ".svg", ".gd", ".gdshader", ".godot", ".tscn"}

# Match values, not the regular expressions used to detect them in this script.
PRIVACY_RULES = (
    ("personal home path", re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+(?:/[^\s\"'<>]*)?")),
    ("personal Windows path", re.compile(r"\b[A-Za-z]:\\{1,2}Users\\{1,2}[A-Za-z0-9_.-]+(?:\\{1,2}[^\s\"'<>]*)?")),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("access token", re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{20,}\b")),
    ("cloud access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("credential literal", re.compile(
        r"\b(?:password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)\b"
        r"\s*[:=]\s*[\"'][A-Za-z0-9_./+=-]{8,}[\"']", re.I)),
)


class ExportError(RuntimeError):
    pass


@dataclass
class RegistrySelection:
    entities: set[tuple[str, str]] = field(default_factory=set)
    variants: set[tuple[str, str, str]] = field(default_factory=set)
    files: set[Path] = field(default_factory=set)


def parse_ref(ref: str) -> tuple[str, str, str]:
    match = REF_RE.fullmatch(ref)
    if not match:
        raise ExportError("invalid starter reference; expected kind/id/vNNN")
    return match.group(1), match.group(2), match.group(3)


def load_manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ExportError("starter manifest must have schema public-alpha/v1")
    packs = data.get("packs")
    if not isinstance(packs, list) or not packs:
        raise ExportError("starter manifest needs at least one pack")
    pack_ids: set[str] = set()
    for pack in packs:
        if not isinstance(pack, dict) or not isinstance(pack.get("id"), str):
            raise ExportError("each starter pack needs an id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", pack["id"]) or pack["id"] in pack_ids:
            raise ExportError("starter pack ids must be unique canonical ids")
        pack_ids.add(pack["id"])
        if not isinstance(pack.get("title"), dict) or not all(
            isinstance(pack["title"].get(locale), str) for locale in ("en", "ru")
        ):
            raise ExportError("starter pack titles need English and Russian text")
        _validate_refs(pack.get("refs"), f"pack {pack['id']}")
    _validate_refs(data.get("demo_refs"), "demo_refs")
    for key in ("materials_refs", "material_preview_refs"):
        if key in data:
            _validate_refs(data[key], key)
    published = {ref for pack in packs for ref in pack["refs"]} | set(data.get("materials_refs", []))
    if not set(data["demo_refs"]).issubset(published):
        raise ExportError("demo_refs must be included in published packs or materials_refs")
    if not set(data.get("material_preview_refs", [])).issubset(published):
        raise ExportError("material previews must be included in published packs")
    return data


def _validate_refs(refs: Any, label: str) -> None:
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
        raise ExportError(f"{label} must be a nonempty reference list")
    if len(refs) != len(set(refs)):
        raise ExportError(f"{label} contains duplicate references")
    for ref in refs:
        parse_ref(ref)


def published_refs(manifest: dict[str, Any]) -> list[str]:
    return sorted({ref for pack in manifest["packs"] for ref in pack["refs"]}
                  | set(manifest.get("materials_refs", [])))


def collect_registry(root: Path, refs: list[str]) -> RegistrySelection:
    """Resolve all parents and slots, including recipes overwritten in descendants."""
    store = Store(root / "registry")
    planner = Planner(store, Config(registry_dir=root / "registry", build_dir=root / "build"))
    result = RegistrySelection()
    queue = [parse_ref(ref) for ref in refs]
    while queue:
        kind, entity_id, vid = queue.pop()
        key = kind, entity_id, vid
        if key in result.variants:
            continue
        try:
            resolution = planner.resolve(kind, entity_id, vid)  # type: ignore[arg-type]
        except (RecipeError, FileNotFoundError) as exc:
            raise ExportError(f"starter dependency cannot be resolved: {'/'.join(key)}") from exc
        if resolution.source is not None:
            raise ExportError(f"manual source is outside this procedural release: {'/'.join(key)}")
        result.variants.add(key)
        result.files.add(Path("registry") / kind / entity_id / "variants" / f"{vid}.yaml")
        queue.extend((kind, entity_id, parent) for parent in resolution.chain)
        for inherited_id in resolution.entity.chain:
            inherited_kind = next((k for k in (kind, *[k for k in KINDS if k != kind])
                                   if store.has_entity(k, inherited_id)), None)
            if inherited_kind is None:
                raise ExportError("entity inheritance could not be located")
            result.entities.add((inherited_kind, inherited_id))
            result.files.add(Path("registry") / inherited_kind / inherited_id / "_base.md")
        folder = Path("registry") / kind / entity_id
        if kind == "components":
            result.files.add(folder / "generator.py")
        elif kind == "materials":
            result.files.add(folder / "blender.py")
            for shader in sorted((root / folder).glob("*.gdshader")):
                result.files.add(shader.relative_to(root))
        if isinstance(resolution, AssetResolution):
            queue.extend((slot.component.entity.kind, slot.component.entity.id, slot.component.variant.id)
                         for slot in resolution.slots.values() if slot.component is not None)
    result.files.add(Path("registry/palette.yaml"))
    # This public finish library is optional for existing recipes, useful for editing.
    presets = Path("registry/material_presets.yaml")
    if (root / presets).is_file():
        result.files.add(presets)
    return result


ROOT_FILES = (
    ".gitignore", "requirements.txt", "requirements-dev.txt", "constraints.txt", "pytest.ini",
    "run.sh", "config.example.yaml", "LICENSE", "LICENSE-ASSETS", "NOTICE",
    "frontend/index.html", "frontend/package.json", "frontend/package-lock.json",
    "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/tests/i18n.test.mjs", "release/starter-packs.yaml",
    "tools/public_release.py", "tools/public_models.py", "tools/blender_checked_launch.py", "tools/blender_checked_exit.py",
    ".github/workflows/ci.yml", ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml", ".github/pull_request_template.md",
)
PUBLIC_DOCUMENTS = {
    "README.md": "README.md", "README.ru.md": "README.ru.md", "AGENTS.md": "AGENTS.md",
    "CLAUDE.md": "AGENTS.md", "CONTRIBUTING.md": "CONTRIBUTING.md", "CHANGELOG.md": "CHANGELOG.md",
    "docs/LICENSE_POLICY.md": "LICENSE_POLICY.md", ".gitignore": "gitignore",
}
IMPRESSOR_DOCUMENTS = (
    "README.md", "ASSET_ITERATION.md", "BLOCKOUT_PRACTICES.md", "PROJECTION_CONTRACT.md",
    "REFERENCE_ITERATION.md", "SKETCH_GENERATION.md",
)
PUBLIC_TESTS = ("tests/test_public_release.py", "tests/test_public_materials.py", "tests/test_public_runtime.py",
                "tests/test_build_failures.py", "tests/test_impressor_sketch.py", "tests/test_public_models.py",
                "tests/test_public_web.py", "tests/test_slot_previews.py", "tests/test_motion_clearance.py")


def source_files(root: Path) -> dict[Path, Path]:
    """Only declared runtime and educational source areas enter the candidate."""
    result: dict[Path, Path] = {}
    for name in ROOT_FILES:
        source = root / name
        if not source.is_file():
            raise ExportError(f"required public source is missing: {name}")
        result[Path(name)] = source
    for destination, template in PUBLIC_DOCUMENTS.items():
        source = root / "docs/public" / template
        if not source.is_file():
            # A published checkout already has the prepared root documentation.
            source = root / destination
        if not source.is_file():
            raise ExportError(f"required public document is missing: {destination}")
        result[Path(destination)] = source
    for directory in ("backend", "builder", "registry", "impressor"):
        for source in sorted((root / directory).glob("*.py")):
            result[source.relative_to(root)] = source
    for name in IMPRESSOR_DOCUMENTS:
        source = root / "impressor" / name
        if source.is_file():
            result[source.relative_to(root)] = source
    trees = (
        ("frontend/src", {".ts", ".css", ".json", ".svg"}),
        ("impressor/templates", {".yaml", ".txt"}),
        ("impressor/examples/truck_cube_r001", {".yaml", ".json", ".txt", ".md", ".png"}),
        ("impressor/examples/truck_cube_sheet_r001", {".yaml", ".json", ".txt", ".md", ".png"}),
        ("docs/guide", {".html", ".json", ".png", ".webp", ".svg", ".yaml", ".txt", ".css", ".js", ".py", ".md"}),
        (".github", {".yml", ".yaml", ".md"}),
        ("tools/godot_check", {".gd", ".godot"}),
        ("tools/godot_preview", {".gd", ".godot"}),
    )
    for directory, suffixes in trees:
        for source in sorted((root / directory).rglob("*")):
            if source.relative_to(root).as_posix() == "docs/guide/assets/reference-lab.png":
                continue
            if source.is_file() and source.suffix in suffixes and not set(source.parts) & PRIVATE_DIRS:
                result[source.relative_to(root)] = source
    for name in PUBLIC_TESTS:
        if (root / name).is_file():
            result[Path(name)] = root / name
    # Prepared templates live in docs/public; a public checkout has only their
    # final docs location. Preserve those same documents when it is re-exported.
    public_docs = root / "docs/public"
    if not public_docs.is_dir():
        public_docs = root / "docs"
    for source in sorted(public_docs.glob("*.html")):
        result[Path("docs") / source.name] = source
    for source in sorted(public_docs.glob("STARTER*.md")):
        result[Path("docs") / source.name] = source
    return result


def copy_source(source: Path, destination: Path, root: Path) -> None:
    if not source.resolve().is_relative_to(root.resolve()) or source.is_symlink():
        raise ExportError("source symlinks and external files are outside the allowlist")
    relative = source.relative_to(root)
    if any((root.joinpath(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts))):
        raise ExportError("source directory symlinks are outside the allowlist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755 if source.suffix == ".sh" else 0o644)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def public_catalog(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    groups = []
    seen: set[str] = set()
    store = Store(root / "registry")
    for pack in manifest["packs"]:
        selection = collect_registry(root, pack["refs"])
        items = [f"{kind}/{eid}" for kind, eid in sorted(selection.entities)
                 if not store.resolve(kind, eid).abstract and f"{kind}/{eid}" not in seen]  # type: ignore[arg-type]
        # The catalog edit API requires one group per entity. Shared plinths still
        # belong to both dependency closures, while appearing once in the UI.
        seen.update(items)
        groups.append({"id": pack["id"], "title": pack["title"]["en"], "items": items})
    return {"groups": groups}


def configure_toon_preview(tree: Path, refs: list[str]) -> bool:
    path = tree / "registry/materials/toon/_base.md"
    if not path.is_file() or not refs:
        return False
    meta, prose = frontmatter.parse(path.read_text(encoding="utf-8"))
    if meta.get("preview") == refs:
        return False
    meta["preview"] = list(refs)
    path.write_text("---\n" + frontmatter.dump_yaml(meta) + "---\n" + prose + "\n", encoding="utf-8")
    return True


def image_metadata_text(data: bytes) -> str:
    """Read image text metadata, never regex-match compressed pixel bytes."""
    texts: list[str] = []
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        while offset + 12 <= len(data):
            length = struct.unpack_from(">I", data, offset)[0]
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + length]
            if len(payload) != length or offset + length + 12 > len(data):
                raise ExportError("malformed PNG metadata")
            try:
                if kind == b"tEXt":
                    texts.append(payload.decode("latin-1"))
                elif kind == b"zTXt":
                    keyword, compressed = payload.split(b"\0", 1)
                    if compressed[:1] != b"\0":
                        raise ValueError("unknown PNG text compression")
                    texts.append(keyword.decode("latin-1") + "\n" + zlib.decompress(compressed[1:]).decode("latin-1"))
                elif kind == b"iTXt":
                    keyword, rest = payload.split(b"\0", 1)
                    flag, method = rest[:2]
                    language, translated, value = rest[2:].split(b"\0", 2)
                    if flag:
                        if method != 0:
                            raise ValueError("unknown PNG text compression")
                        value = zlib.decompress(value)
                    texts.append("\n".join(part.decode("utf-8") for part in (keyword, language, translated, value)))
                elif kind == b"eXIf":
                    texts.append(payload.decode("latin-1"))
            except (ValueError, UnicodeError, zlib.error) as exc:
                raise ExportError("cannot inspect image text metadata") from exc
            offset += length + 12
            if kind == b"IEND":
                break
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        offset = 12
        while offset + 8 <= len(data):
            kind = data[offset:offset + 4]
            length = struct.unpack_from("<I", data, offset + 4)[0]
            payload = data[offset + 8:offset + 8 + length]
            if len(payload) != length:
                raise ExportError("malformed WebP metadata")
            if kind in (b"EXIF", b"XMP "):
                texts.append(payload.decode("latin-1"))
            offset += 8 + length + length % 2
    else:
        raise ExportError("unsupported binary in the public source allowlist")
    return "\n".join(texts)


def privacy_findings(tree: Path, deny_terms: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(tree.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(tree)
        if path.is_symlink() or set(relative.parts) & PRIVATE_DIRS or path.suffix in PRIVATE_SUFFIXES:
            findings.append({"path": relative.as_posix(), "category": "excluded file or directory"})
            continue
        content = path.read_bytes()
        try:
            source = content.decode("utf-8")
        except UnicodeError:
            source = image_metadata_text(content)
        for category, rule in PRIVACY_RULES:
            match = rule.search(source)
            if match:
                findings.append({"path": relative.as_posix(), "category": category,
                                 "line": source.count("\n", 0, match.start()) + 1})
        for term in deny_terms:
            if term and term.casefold() in source.casefold():
                findings.append({"path": relative.as_posix(), "category": "owner-provided excluded term"})
    return findings


def verify_tree(tree: Path, *, verify_hashes: bool = True) -> dict[str, int]:
    manifest = load_manifest(tree / "release/starter-packs.yaml")
    selection = collect_registry(tree, published_refs(manifest))
    findings = privacy_findings(tree)
    if findings:
        raise ExportError("privacy gate failed: " + json.dumps(findings, ensure_ascii=False))
    cfg = Config(registry_dir=tree / "registry", build_dir=tree / "build", db_path=tree / "var/index.sqlite")
    if cmd_check(cfg, argparse.Namespace()) != 0:
        raise ExportError("public registry validation failed")
    seed = tree / "backend/seed/registry"
    actual = {p.relative_to(tree / "registry"): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (tree / "registry").rglob("*") if p.is_file()
              and p.relative_to(tree / "registry") not in (Path("__init__.py"), Path("__main__.py"))}
    seeded = {p.relative_to(seed): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in seed.rglob("*") if p.is_file()}
    if actual != seeded:
        raise ExportError("public seed differs from the public registry")
    if verify_hashes:
        record = json.loads((tree / CONTENT_MANIFEST).read_text(encoding="utf-8"))
        if record.get("schema") != EXPORT_SCHEMA:
            raise ExportError("missing public export marker")
        expected = {item["path"]: item for item in record["files"]}
        actual_paths = {p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file()
                        and p.relative_to(tree).as_posix() != CONTENT_MANIFEST}
        if actual_paths != set(expected):
            raise ExportError("public content manifest file list differs")
        for name, item in expected.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ExportError("public content manifest contains an unsafe path")
            path = tree / name
            if len(path.read_bytes()) != item["size"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ExportError(f"public content changed after export: {name}")
    return {"entities": len(selection.entities), "variants": len(selection.variants), "files": len(actual)}


def content_manifest(tree: Path, selection: RegistrySelection, transforms: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for path in sorted(tree.rglob("*")):
        if path.is_file() and path.relative_to(tree).as_posix() != CONTENT_MANIFEST:
            content = path.read_bytes()
            entries.append({"path": path.relative_to(tree).as_posix(), "sha256": hashlib.sha256(content).hexdigest(),
                            "size": len(content)})
    return {"schema": EXPORT_SCHEMA, "registry": {"entities": len(selection.entities),
            "variants": len(selection.variants)}, "transforms": transforms, "files": entries}


def deterministic_zip(tree: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for path in sorted(tree.rglob("*")):
                if not path.is_file():
                    continue
                name = (Path(tree.name) / path.relative_to(tree)).as_posix()
                item = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                item.create_system = 3
                mode = 0o755 if path.suffix == ".sh" else 0o644
                item.external_attr = (stat.S_IFREG | mode) << 16
                item.compress_type = zipfile.ZIP_DEFLATED
                output.writestr(item, path.read_bytes(), compresslevel=9)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)


def export_public(root: Path, destination: Path, *, archive: Path | None = None,
                  deny_terms: tuple[str, ...] = ()) -> dict[str, int]:
    root = root.resolve()
    destination = destination.absolute()
    allowed = root / "var/public-alpha"
    if not destination.resolve().is_relative_to(allowed.resolve()) or destination.resolve() == allowed.resolve():
        raise ExportError("export destination must be a child of var/public-alpha")
    if destination.is_symlink():
        raise ExportError("export destination cannot be a symlink")
    if destination.exists():
        marker = destination / CONTENT_MANIFEST
        if not marker.is_file() or json.loads(marker.read_text()).get("schema") != EXPORT_SCHEMA:
            raise ExportError("refusing to replace a directory without an export marker")
    if archive is not None:
        if not archive.resolve().is_relative_to(allowed.resolve()) or archive.resolve().is_relative_to(destination.resolve()):
            raise ExportError("archive must be inside var/public-alpha and outside the candidate tree")
    manifest = load_manifest(root / "release/starter-packs.yaml")
    selection = collect_registry(root, published_refs(manifest))
    sources = source_files(root)
    sources.update((relative, root / relative) for relative in selection.files)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".public-stage-", dir=destination.parent))
    try:
        for relative, source in sorted(sources.items()):
            if not source.is_file():
                raise ExportError(f"required dependency is missing: {relative.as_posix()}")
            copy_source(source, stage / relative, root)
        copy_source(root / "config.example.yaml", stage / "config.yaml", root)
        transforms: list[dict[str, Any]] = [{"path": "config.yaml", "change": "public example defaults"}]
        if configure_toon_preview(stage, manifest.get("material_preview_refs", [])):
            transforms.append({"path": "registry/materials/toon/_base.md", "change": "pin previews to starter models"})
        groups = public_catalog(root, manifest)
        (stage / "registry/catalog_groups.yaml").write_text(frontmatter.dump_yaml(groups), encoding="utf-8")
        transforms.append({"path": "registry/catalog_groups.yaml", "change": "only starter pack entities"})
        # Seed the published checkout, not the private workspace's backend/seed.
        shutil.copytree(stage / "registry", stage / "backend/seed/registry",
                        ignore=shutil.ignore_patterns("__init__.py", "__main__.py"))
        # Registry is both a CLI package and a data root. Package files aren't seed data.
        seed = stage / "backend/seed/registry"
        (seed / "__init__.py").unlink(missing_ok=True)
        (seed / "__main__.py").unlink(missing_ok=True)
        findings = privacy_findings(stage, deny_terms)
        if findings:
            raise ExportError("privacy gate failed: " + json.dumps(findings, ensure_ascii=False))
        write_json(stage / CONTENT_MANIFEST, content_manifest(stage, selection, transforms))
        summary = verify_tree(stage)
        if destination.exists():
            shutil.rmtree(destination)
        stage.replace(destination)
        if archive is not None:
            deterministic_zip(destination, archive)
        return summary
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify a curated public alpha; never publish")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "var/public-alpha/voxel-asset-registry")
    parser.add_argument("--zip", type=Path, dest="archive", default=PROJECT_ROOT / "var/public-alpha/voxel-asset-registry-alpha.zip")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--verify", type=Path, help="verify an existing unchanged candidate")
    parser.add_argument("--deny-term", action="append", default=[], help="extra owner-provided term to exclude")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            summary = verify_tree(args.verify.resolve())
        else:
            summary = export_public(PROJECT_ROOT, args.out, archive=None if args.no_zip else args.archive,
                                    deny_terms=tuple(args.deny_term))
        print(json.dumps({"status": "ok", **summary}, sort_keys=True))
        return 0
    except (ExportError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"public export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
