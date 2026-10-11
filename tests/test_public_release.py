"""The public exporter must preserve dependencies and fail closed on private data."""

import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path

import pytest
import yaml

from tools.public_release import (
    CONTENT_MANIFEST,
    PUBLIC_DOCUMENTS,
    ROOT_FILES,
    ExportError,
    collect_registry,
    deterministic_zip,
    export_public,
    load_manifest,
    privacy_findings,
    public_catalog,
    verify_tree,
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fixture_registry(root: Path) -> None:
    write(root / "registry/palette.yaml", "voxel_size: 0.25\ncolors: {steel: '#808080'}\n")
    for entity in ("body", "old_part", "new_part"):
        write(root / f"registry/components/{entity}/_base.md", f"""---
id: {entity}
interface: {{grid_size: [4, 4, 4], voxel_size: 0.25, pivot: bottom_center}}
params: {{size: {{type: float, default: 0.5, min: 0.25, max: 1.0}}}}
---
Public fixture.
""")
        write(root / f"registry/components/{entity}/generator.py", "def build(params):\n    return None\n")
        write(root / f"registry/components/{entity}/variants/v001.yaml",
              "id: v001\nparent: null\ndelta: {}\nlevel: 1\nauthor: llm\n")
    write(root / "registry/components/body/variants/v002.yaml",
          "id: v002\nparent: v001\ndelta: {size: 0.75}\nlevel: 1\nauthor: llm\n")
    write(root / "registry/assets/family/_base.md", """---
id: family
abstract: true
interface: {grid_size: [8, 8, 8], voxel_size: 0.25, pivot: bottom_center}
slots:
  body: {socket: null, max_grid: [8, 8, 8]}
  detail: {socket: null, max_grid: [8, 8, 8]}
---
Public abstract family.
""")
    write(root / "registry/assets/truck/_base.md", "---\nid: truck\ninherits: family\n---\nPublic truck.\n")
    write(root / "registry/assets/truck/variants/v001.yaml", """id: v001
parent: null
slots: {body: body@v002, detail: old_part@v001}
level: 1
author: llm
""")
    write(root / "registry/assets/truck/variants/v002.yaml", """id: v002
parent: v001
slots: {detail: new_part@v001}
level: 1
author: llm
""")


def fixture_release(root: Path) -> None:
    fixture_registry(root)
    for name in ROOT_FILES:
        write(root / name, "# Public source fixture\n")
    for name in set(PUBLIC_DOCUMENTS.values()):
        write(root / "docs/public" / name, "Public project documentation.\n")
    write(root / "config.example.yaml", "legacy: {sources: []}\n")
    manifest = {"schema": "public-alpha/v1", "demo_refs": ["assets/truck/v002"],
                "packs": [{"id": "truck", "title": {"en": "Truck", "ru": "Грузовик"},
                           "refs": ["assets/truck/v002"]}]}
    write(root / "release/starter-packs.yaml", yaml.safe_dump(manifest, allow_unicode=True))
    write(root / "registry/__init__.py", "")
    write(root / "registry/__main__.py", "")


def test_closure_includes_overwritten_parent_slots_and_entity_inheritance(tmp_path):
    fixture_registry(tmp_path)
    selected = collect_registry(tmp_path, ["assets/truck/v002"])
    assert ("assets", "family") in selected.entities
    assert ("components", "old_part", "v001") in selected.variants
    assert ("components", "new_part", "v001") in selected.variants
    assert ("components", "body", "v001") in selected.variants
    assert len(selected.variants) == 6


def test_public_catalog_deduplicates_components_shared_by_packs(tmp_path):
    fixture_release(tmp_path)
    manifest = load_manifest(tmp_path / "release/starter-packs.yaml")
    manifest["packs"].append({"id": "comparison", "title": {"en": "Comparison", "ru": "Сравнение"},
                              "refs": ["assets/truck/v001"]})
    items = [item for group in public_catalog(tmp_path, manifest)["groups"] for item in group["items"]]
    assert len(items) == len(set(items))
    assert "assets/family" not in items


def test_manual_source_is_rejected_without_copying_binary(tmp_path):
    fixture_registry(tmp_path)
    path = tmp_path / "registry/components/new_part/variants/v001.yaml"
    write(path, "id: v001\nsource: custom.blend\nlevel: 1\nauthor: human\n")
    (path.parent / "custom.blend").write_bytes(b"fixture")
    with pytest.raises(ExportError, match="manual source"):
        collect_registry(tmp_path, ["assets/truck/v002"])


def test_privacy_gate_reports_categories_without_echoing_values(tmp_path):
    personal_path = "/" + "home" + "/" + "private-owner" + "/project"
    address = "private-owner" + "@" + "example.org"
    token = "sk" + "-" + "x" * 32
    write(tmp_path / "notes.txt", personal_path + "\n" + address + "\n" + token)
    findings = privacy_findings(tmp_path)
    assert {f["category"] for f in findings} == {"personal home path", "email address", "access token"}
    rendered = json.dumps(findings)
    assert personal_path not in rendered
    assert address not in rendered
    assert token not in rendered


def test_privacy_gate_catches_json_escaped_windows_home_paths(tmp_path):
    personal_path = "C:" + "\\Users\\" + "private-owner" + "\\project"
    write(tmp_path / "metadata.json", json.dumps({"source": personal_path}))
    assert privacy_findings(tmp_path)[0]["category"] == "personal Windows path"


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def test_image_gate_scans_metadata_without_matching_pixel_data(tmp_path):
    address = "private-owner" + "@" + "example.org"
    prefix = b"\x89PNG\r\n\x1a\n"
    # Matching strings inside pixel chunks have no meaning as personal metadata.
    (tmp_path / "pixels.png").write_bytes(prefix + png_chunk(b"IDAT", address.encode()) + png_chunk(b"IEND", b""))
    assert privacy_findings(tmp_path) == []
    (tmp_path / "metadata.png").write_bytes(prefix + png_chunk(b"tEXt", b"Author\0" + address.encode())
                                            + png_chunk(b"IEND", b""))
    assert privacy_findings(tmp_path) == [{"path": "metadata.png", "category": "email address", "line": 1}]


def test_public_tree_and_seed_are_complete_without_private_workspace_files(tmp_path):
    fixture_release(tmp_path)
    write(tmp_path / "references/secret.txt", "private")
    write(tmp_path / "impressor/iterations/private.txt", "private")
    write(tmp_path / "backend/seed/registry/private.txt", "private seed")
    write(tmp_path / "config.yaml", "server: {port: 9999}\n")
    destination = tmp_path / "var/public-alpha/project"
    result = export_public(tmp_path, destination)
    assert result["entities"] == 5
    assert result["variants"] == 6
    assert (destination / "config.yaml").read_text() == "legacy: {sources: []}\n"
    assert not (destination / "references").exists()
    assert not (destination / "impressor/iterations").exists()
    assert not (destination / "backend/seed/registry/private.txt").exists()
    assert (tmp_path / "backend/seed/registry/private.txt").read_text() == "private seed"
    assert verify_tree(destination) == result
    assert (destination / "backend/seed/registry/components/old_part/variants/v001.yaml").is_file()
    # Modified public files are detected before somebody treats the manifest as verified.
    write(destination / "README.md", "Changed documentation.\n")
    with pytest.raises(ExportError, match="content changed"):
        verify_tree(destination)


def test_failed_privacy_gate_preserves_previous_candidate(tmp_path):
    fixture_release(tmp_path)
    destination = tmp_path / "var/public-alpha/project"
    export_public(tmp_path, destination)
    before = (destination / CONTENT_MANIFEST).read_bytes()
    write(tmp_path / "docs/public/README.md", "/" + "home" + "/" + "private-owner" + "/project\n")
    with pytest.raises(ExportError, match="privacy gate failed"):
        export_public(tmp_path, destination)
    assert (destination / CONTENT_MANIFEST).read_bytes() == before
    assert not list(destination.parent.glob(".public-stage-*"))


def test_published_checkout_reexport_preserves_complete_file_inventory(tmp_path):
    fixture_release(tmp_path)
    write(tmp_path / "docs/public/STARTER_PACKS.md", "Public starter pack usage.\n")
    write(tmp_path / "docs/public/STARTER_ROADMAP.md", "Public starter roadmap.\n")
    write(tmp_path / "docs/public/overview.html", "<p>Public overview.</p>\n")
    first = tmp_path / "var/public-alpha/project"
    export_public(tmp_path, first)
    first_manifest = json.loads((first / CONTENT_MANIFEST).read_text())
    assert not (first / "docs/public").exists()
    second = first / "var/public-alpha/project"
    export_public(first, second)
    second_manifest = json.loads((second / CONTENT_MANIFEST).read_text())
    assert second_manifest["files"] == first_manifest["files"]
    assert verify_tree(second)["variants"] == 6


def test_export_refuses_unmarked_existing_destination_and_unsafe_refs(tmp_path):
    fixture_release(tmp_path)
    destination = tmp_path / "var/public-alpha/project"
    destination.mkdir(parents=True)
    write(destination / "keep.txt", "keep")
    with pytest.raises(ExportError, match="without an export marker"):
        export_public(tmp_path, destination)
    path = tmp_path / "release/starter-packs.yaml"
    data = yaml.safe_load(path.read_text())
    data["packs"][0]["refs"] = ["assets/../../private/v001"]
    write(path, yaml.safe_dump(data))
    with pytest.raises(ExportError, match="invalid starter reference"):
        load_manifest(path)


def test_archive_is_deterministic_and_contains_only_relative_paths(tmp_path):
    tree = tmp_path / "project"
    write(tree / "README.md", "Public text\n")
    write(tree / "run.sh", "#!/usr/bin/env bash\n")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    deterministic_zip(tree, first)
    deterministic_zip(tree, second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["project/README.md", "project/run.sh"]
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in archive.namelist())


def test_source_symlink_is_not_followed(tmp_path):
    fixture_release(tmp_path)
    outside = tmp_path.parent / (tmp_path.name + "-outside.txt")
    outside.write_text("external content", encoding="utf-8")
    try:
        path = tmp_path / "README.ru.md"
        path.symlink_to(outside)
        (tmp_path / "docs/public/README.ru.md").unlink()
        with pytest.raises(ExportError, match="symlinks"):
            export_public(tmp_path, tmp_path / "var/public-alpha/project")
    finally:
        outside.unlink(missing_ok=True)
