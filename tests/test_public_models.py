"""Built model release attachments must be complete, deterministic and private."""

import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path

import pytest
import yaml

from backend.config import Config
from backend.planner import Planner
from backend.store import Store
from builder.projection_views import PREVIEW_FILES
from tools import public_models
from tools.public_release import ExportError


def png(text: bytes | None = None) -> bytes:
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    result = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    if text is not None:
        result += chunk(b"tEXt", b"Author\0" + text)
    return result + chunk(b"IDAT", zlib.compress(bytes([0, 128, 128, 128]))) + chunk(b"IEND", b"")


def glb(extra=None, *, texture: bytes | None = None) -> bytes:
    """A glTF 2.0 indexed triangle with an embedded binary vertex/index buffer."""
    binary = struct.pack("<9f3H", 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 2)
    binary += bytes((-len(binary)) % 4)
    document = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                        {"buffer": 0, "byteOffset": 36, "byteLength": 6}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                       "min": [0, 0, 0], "max": [1, 1, 1]},
                      {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}],
    }
    if texture is not None:
        document["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(texture)})
        document["images"] = [{"bufferView": 2, "mimeType": "image/png"}]
        binary += texture
        binary += bytes((-len(binary)) % 4)
        document["buffers"][0]["byteLength"] = len(binary)
    if extra:
        document.update(extra)
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * ((-len(encoded)) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(binary))
            + struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


@pytest.fixture
def built_public(tmp_path, monkeypatch):
    monkeypatch.setattr(public_models, "PROJECT_ROOT", tmp_path)
    source = tmp_path / "source"
    folder = source / "registry/components/crate"
    (folder / "variants").mkdir(parents=True)
    (source / "registry/palette.yaml").write_text("voxel_size: 0.25\ncolors: {steel: '#808080'}\n")
    (folder / "_base.md").write_text("---\nid: crate\ngenerator_version: 1\n"
                                    "interface: {grid_size: [4, 4, 4], voxel_size: 0.25}\nparams: {}\n---\n")
    (folder / "generator.py").write_text("def build(params): return None\n")
    for vid in ("v001", "v002"):
        # Both aliases intentionally use the same geometry hash.
        (folder / "variants" / f"{vid}.yaml").write_text(f"id: {vid}\nlevel: 1\ndelta: {{}}\n")
    (source / "release").mkdir()
    refs = ["components/crate/v001", "components/crate/v002"]
    (source / "release/starter-packs.yaml").write_text(yaml.safe_dump({
        "schema": "public-alpha/v1", "demo_refs": [refs[0]],
        "packs": [{"id": "crates", "title": {"en": "Crates", "ru": "Ящики"}, "refs": refs}],
        "materials_refs": ["materials/toon/v001"],
    }))
    (source / "LICENSE-ASSETS").write_text("CC0 public asset fixture\n")
    (source / "NOTICE").write_text("Public starter models fixture\n")
    planner = Planner(Store(source / "registry"), Config(registry_dir=source / "registry", build_dir=source / "build"))
    digest = planner.resolve_component("crate", "v001").hash
    artifact = source / "build" / digest
    artifact.mkdir(parents=True)
    report = {"hash": digest, "kind": "components", "id": "crate", "variant": "v001", "status": "ok",
              "checks": [{"name": "geometry", "ok": True, "message": "private detail excluded"}],
              "stats": {"bbox_m": [1, 1, 1], "vertices": 3, "triangles": 1,
                        "sockets": [{"name": "top", "position": [0, 1, 0], "description": "excluded"}]},
              "log_tail": ["private log excluded"], "recipe_path": "excluded"}
    (artifact / "report.json").write_text(json.dumps(report))
    (artifact / "model.glb").write_bytes(glb(texture=png()))
    for name in PREVIEW_FILES:
        (artifact / name).write_bytes(png())
    # Unrelated files and historical caches must never enter the attachment.
    (artifact / "build.log").write_text("private log fixture\n")
    (artifact / "recipe.json").write_text('{"source": "private fixture"}')
    (source / "build/unrelated").mkdir()
    (source / "build/unrelated/private.glb").write_bytes(b"unrelated")
    out = tmp_path / "var/public-alpha/starter-models.zip"
    return source, artifact, out


def test_archive_contains_only_selected_models_and_sanitised_metadata_with_hashes(built_public):
    source, _artifact, out = built_public
    result = public_models.export_models(source, out)
    assert result["models"] == 2
    assert result["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    first = out.read_bytes()
    public_models.export_models(source, out)
    assert out.read_bytes() == first
    with zipfile.ZipFile(out) as archive:
        index = json.loads(archive.read("index.json"))
        assert len(index["models"]) == 2
        assert index["starter_manifest_sha256"] == hashlib.sha256(
            (source / "release/starter-packs.yaml").read_bytes()
        ).hexdigest()
        assert set(archive.namelist()) == {"index.json", *[item["path"] for item in index["files"]]}
        for item in index["files"]:
            payload = archive.read(item["path"])
            assert item["sha256"] == hashlib.sha256(payload).hexdigest()
            assert item["size"] == len(payload)
        for model in index["models"]:
            assert len(model["previews"]) == 7
            metadata = archive.read(model["path"].replace("model.glb", "metadata.json")).decode()
            assert "private" not in metadata and "description" not in metadata
        assert not any("recipe.json" in name or "build.log" in name or "unrelated" in name for name in archive.namelist())
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in archive.namelist())


@pytest.mark.parametrize("failure", ["failed", "missing_model", "missing_projection", "failed_check", "wrong_hash"])
def test_incomplete_or_failed_model_preserves_existing_archive(built_public, failure):
    source, artifact, out = built_public
    public_models.export_models(source, out)
    original = out.read_bytes()
    report = json.loads((artifact / "report.json").read_text())
    if failure == "failed":
        report["status"] = "failed"
    elif failure == "failed_check":
        report["checks"][0]["ok"] = False
    elif failure == "wrong_hash":
        report["hash"] = "0" * 16
    elif failure == "missing_model":
        (artifact / "model.glb").unlink()
    else:
        (artifact / PREVIEW_FILES[-1]).unlink()
    (artifact / "report.json").write_text(json.dumps(report))
    with pytest.raises(ExportError):
        public_models.export_models(source, out)
    assert out.read_bytes() == original


@pytest.mark.parametrize("uri", ["texture.png", "https://example.org/texture.png", "file:///private/file.png"])
def test_glb_resource_uris_are_rejected(uri):
    with pytest.raises(ExportError, match="URIs"):
        public_models.validate_glb(glb({"images": [{"uri": uri}]}))


def test_glb_private_json_and_embedded_image_metadata_are_rejected():
    address = "private-owner" + "@" + "example.org"
    with pytest.raises(ExportError, match="privacy"):
        public_models.validate_glb(glb({"extras": {"author": address}}))
    with pytest.raises(ExportError, match="privacy"):
        public_models.validate_glb(glb(texture=png(address.encode())))
    with pytest.raises(ExportError, match="header"):
        public_models.validate_glb(b"not a model")


@pytest.mark.parametrize("private_path", ["/" + "home/owner/model.blend", "C:" + "\\Users\\owner\\model.blend"])
def test_glb_decoded_home_paths_are_rejected(private_path):
    with pytest.raises(ExportError, match="privacy"):
        public_models.validate_glb(glb({"extras": {"source": private_path}}))


def test_projection_private_metadata_is_rejected(built_public):
    source, artifact, out = built_public
    address = "private-owner" + "@" + "example.org"
    (artifact / PREVIEW_FILES[0]).write_bytes(png(address.encode()))
    with pytest.raises(ExportError, match="privacy"):
        public_models.export_models(source, out)
    assert not out.exists()


def test_symlink_and_unsafe_output_are_rejected(built_public):
    source, artifact, out = built_public
    model = artifact / "model.glb"
    value = model.read_bytes()
    outside = source.parent / "outside.glb"
    outside.write_bytes(value)
    model.unlink()
    model.symlink_to(outside)
    with pytest.raises(ExportError, match="symlink"):
        public_models.export_models(source, out)
    with pytest.raises(ExportError, match="inside var/public-alpha"):
        public_models.export_models(source, source.parent / "outside.zip")
    assert not out.exists()


def test_unmarked_archive_is_not_overwritten(built_public):
    source, _artifact, out = built_public
    out.parent.mkdir(parents=True)
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("unrelated.txt", "must survive")
    original = out.read_bytes()
    with pytest.raises(ExportError, match="marker"):
        public_models.export_models(source, out)
    assert out.read_bytes() == original
