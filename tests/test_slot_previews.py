"""Compose options expose only previews that exist in the current build cache."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import Config
from backend.planner import Planner
from backend.store import Store


@pytest.fixture
def compose(tmp_path):
    registry = tmp_path / "registry"
    part = registry / "components/crate"
    asset = registry / "assets/container"
    for folder in (part, asset):
        (folder / "variants").mkdir(parents=True)
    (registry / "palette.yaml").write_text("voxel_size: 0.25\ncolors: {steel: '#808080'}\n")
    (part / "_base.md").write_text(
        "---\nid: crate\ngenerator_version: 1\n"
        "interface: {grid_size: [4, 4, 4], voxel_size: 0.25}\nparams: {}\n---\n"
    )
    (part / "generator.py").write_text("def build(params): return None\n")
    for variant, status in (("v001", "approved"), ("v002", "built")):
        (part / "variants" / f"{variant}.yaml").write_text(
            f"id: {variant}\nstatus: {status}\nlevel: 1\ndelta: {{}}\n"
        )
    (asset / "_base.md").write_text(
        "---\nid: container\ninterface: {grid_size: [8, 8, 8], voxel_size: 0.25}\n"
        "slots:\n  body: {socket: null, max_grid: [8, 8, 8]}\n"
        "  detail: {socket: null, max_grid: [8, 8, 8], required: false}\n---\n"
    )
    (asset / "variants/v001.yaml").write_text("id: v001\nslots: {body: crate@v001, detail: null}\n")
    cfg = Config(registry_dir=registry, build_dir=tmp_path / "build", db_path=tmp_path / "index.sqlite")
    digest = Planner(Store(registry), cfg).resolve_component("crate", "v001").hash
    folder = cfg.build_dir / digest
    folder.mkdir(parents=True)
    app = create_app(cfg)
    original = {path: path.read_bytes() for path in registry.rglob("*") if path.is_file()}
    yield app, TestClient(app), digest, folder
    assert original == {path: path.read_bytes() for path in registry.rglob("*") if path.is_file()}
    app.state.index.engine.dispose()


def options(client):
    response = client.get("/api/assets/container/slot-options")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["body"]) == len(data["detail"]) == 2
    assert {item["status"] for item in data["body"]} == {"built", "approved"}
    return [item for items in data.values() for item in items]


def test_cold_checkout_keeps_options_without_inventing_preview_urls(compose):
    _app, client, digest, _folder = compose
    for item in options(client):
        assert item["hash"] == digest
        assert item["build_state"] == "none"
        assert item["preview"] is None


def test_successful_report_without_projection_has_no_preview(compose):
    _app, client, _digest, folder = compose
    (folder / "report.json").write_text(json.dumps({"status": "ok"}))
    (folder / "model.glb").write_bytes(b"model artifact fixture")
    assert all(item["build_state"] == "ok" and item["preview"] is None for item in options(client))


def test_available_preview_is_served_and_refreshed_per_request(compose, monkeypatch):
    app, client, digest, folder = compose
    (folder / "report.json").write_text(json.dumps({"status": "ok", "built_at": "2026-10-11T12:00:00+00:00"}))
    (folder / "preview_iso.png").write_bytes(b"projection artifact fixture")
    reads = []
    read_report = app.state.builds.read_report

    def counted(value):
        reads.append(value)
        return read_report(value)

    monkeypatch.setattr(app.state.builds, "read_report", counted)
    items = options(client)
    assert reads == [digest]  # Four references to one build share one disk read.
    for item in items:
        assert item["preview"] == f"/api/builds/{digest}/preview_iso.png?v=202610111200000000"
        assert client.get(item["preview"]).status_code == 200
    (folder / "preview_iso.png").unlink()
    assert all(item["preview"] is None for item in options(client))
    assert reads == [digest, digest]


@pytest.mark.parametrize("state", ["failed", "queued", "running"])
def test_failed_or_active_build_has_no_preview_even_with_stale_file(compose, state):
    app, client, digest, folder = compose
    (folder / "report.json").write_text(json.dumps({"status": "failed" if state == "failed" else "ok"}))
    (folder / "preview_iso.png").write_bytes(b"stale projection fixture")
    if state != "failed":
        app.state.builds.jobs[digest] = SimpleNamespace(state=state)
    assert all(item["build_state"] == state and item["preview"] is None for item in options(client))
