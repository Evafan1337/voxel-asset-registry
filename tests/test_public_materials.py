"""Material previews can pin complete demo models instead of newest kit pieces."""

import json
from pathlib import Path

from backend.config import Config
from backend.planner import Planner
from backend.store import Store


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def prepared_models(root: Path) -> tuple[Store, Planner]:
    write(root / "registry/palette.yaml", "voxel_size: 0.25\ncolors: {steel: '#808080'}\n")
    write(root / "registry/components/vehicle/_base.md", """---
id: vehicle
interface: {grid_size: [4, 4, 4], voxel_size: 0.25, pivot: bottom_center}
params: {stage: {type: int, default: 1, min: 1, max: 3}}
---
Public vehicle fixture.
""")
    for vid, status, stage in (("v001", "draft", 1), ("v002", "approved", 2), ("v003", "built", 3)):
        write(root / f"registry/components/vehicle/variants/{vid}.yaml",
              f"id: {vid}\nparent: null\ndelta: {{stage: {stage}}}\nlevel: 1\nauthor: llm\nstatus: {status}\n")
    write(root / "registry/materials/toon/_base.md", "---\nid: toon\npreview: []\nparams: {}\n---\n")
    cfg = Config(registry_dir=root / "registry", build_dir=root / "build")
    store = Store(cfg.registry_dir)
    planner = Planner(store, cfg)
    for vid in ("v001", "v002", "v003"):
        resolved = planner.resolve_component("vehicle", vid)
        folder = cfg.build_dir / resolved.hash
        folder.mkdir(parents=True)
        (folder / "model.glb").write_bytes(b"test-built-model")
        write(folder / "report.json", json.dumps({"status": "ok"}))
    return store, planner


def test_pinned_preview_uses_requested_variant_even_when_another_is_approved(tmp_path):
    store, planner = prepared_models(tmp_path)
    entity = store.resolve("materials", "toon").model_copy(update={"preview": ["components/vehicle/v001"]})
    assert [m["ref"] for m in planner.preview_models(entity)] == ["components/vehicle@v001"]


def test_unpinned_preview_preserves_approved_then_newest_selection(tmp_path):
    store, planner = prepared_models(tmp_path)
    entity = store.resolve("materials", "toon").model_copy(update={"preview": ["components/vehicle"]})
    assert [m["ref"] for m in planner.preview_models(entity)] == ["components/vehicle@v002"]


def test_missing_pinned_variant_does_not_fall_back_to_a_different_model(tmp_path):
    store, planner = prepared_models(tmp_path)
    entity = store.resolve("materials", "toon").model_copy(update={"preview": ["components/vehicle/v099"]})
    assert planner.preview_models(entity) == []
