"""Clean-checkout setup contracts, using only small temporary registry fixtures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from backend import cli, config, preflight
from backend.config import Config, Legacy
from backend.planner import Planner
from backend.store import Store
from backend.preflight import Check, checks_ok, environment_checks, node_supported, starter_targets


@pytest.fixture
def small_registry(tmp_path):
    root = tmp_path / "registry"
    folder = root / "components" / "crate"
    (folder / "variants").mkdir(parents=True)
    (root / "palette.yaml").write_text("voxel_size: 0.25\ncolors: {steel: '#808080'}\n")
    (folder / "_base.md").write_text(
        "---\nid: crate\ntitle: Test crate\ngenerator_version: 1\n"
        "interface: {grid_size: [4, 4, 4], voxel_size: 0.25}\nparams: {}\n---\n"
    )
    (folder / "generator.py").write_text("def build(params): return None\n")
    (folder / "variants" / "v001.yaml").write_text("id: v001\nlevel: 0\ndelta: {}\n")
    (folder / "variants" / "v002.yaml").write_text("id: v002\nparent: v001\nlevel: 1\ndelta: {}\n")
    cfg = Config(registry_dir=root, build_dir=tmp_path / "build", db_path=tmp_path / "var/index.sqlite")
    manifest = tmp_path / "starter.yaml"
    manifest.write_text(yaml.safe_dump({
        "schema": "public-alpha/v1", "demo_refs": ["components/crate/v001"],
        "packs": [{"id": "crates", "refs": ["components/crate/v001", "components/crate/v002"]}],
    }))
    return cfg, manifest


@pytest.mark.parametrize("version, expected", [
    ((18, 20, 0), False), ((20, 18, 9), False), ((20, 19, 0), True), ((20, 30, 0), True),
    ((21, 9, 0), False), ((22, 11, 9), False), ((22, 12, 0), True), ((24, 14, 0), True),
])
def test_node_range_matches_locked_frontend(version, expected):
    assert node_supported(version) is expected


def test_local_config_merges_nested_settings_and_saves_only_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.delenv("REGISTRY_CONFIG", raising=False)
    base = tmp_path / "config.yaml"
    base.write_text("server: {host: 127.0.0.1, port: 8000}\npriority_tags: [base]\n"
                    "legacy: {sources: [{name: old, label: Old, path: outside}]}\n")
    original = base.read_bytes()
    local = tmp_path / "config.local.yaml"
    local.write_text("server: {port: 8123}\nlegacy: {sources: []}\n")
    cfg = config.load_config()
    assert cfg.server.host == "127.0.0.1" and cfg.server.port == 8123
    assert cfg.legacy.sources == []
    assert cfg.registry_dir == tmp_path / "registry"
    config.save_priority_tags(cfg, ["local"])
    assert base.read_bytes() == original
    assert config.load_config().priority_tags == ["local"]
    assert yaml.safe_load(local.read_text())["server"] == {"port": 8123}


def test_explicit_config_bypasses_local_overrides_and_empty_defaults_do_not_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config.local.yaml").write_text("server: {port: 9000}\n")
    explicit = tmp_path / "chosen.yaml"
    explicit.write_text("server: {port: 8123}\n")
    monkeypatch.setenv("REGISTRY_CONFIG", str(explicit))
    assert config.load_config().server.port == 8123
    assert config.load_config(explicit).legacy.sources == []
    assert Legacy().sources == []
    assert Config().godot_vulkan_icd == ""


def test_sample_config_is_used_when_default_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.delenv("REGISTRY_CONFIG", raising=False)
    (tmp_path / "config.example.yaml").write_text("server: {port: 8123}\n")
    assert config.load_config().server.port == 8123
    (tmp_path / "invalid.yaml").write_text("[not, a, mapping]\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        config.load_config(tmp_path / "invalid.yaml")


def test_doctor_can_skip_blender_without_claiming_it_was_checked(small_registry, monkeypatch, capsys):
    cfg, _manifest = small_registry
    calls = []

    def probe(binary, _pattern):
        calls.append(binary)
        assert binary != cfg.blender_bin
        return None, "executable not found"

    monkeypatch.setattr(preflight, "_probe", probe)
    checks = environment_checks(cfg, frontend=False, skip_blender=True)
    assert checks_ok(checks)
    assert all(check.name != "blender" for check in checks)
    preflight.render_checks(checks, as_json=True)
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert not cfg.build_dir.exists() and not cfg.db_path.parent.exists()


def test_doctor_requires_blender_only_when_requested(small_registry, monkeypatch):
    cfg, _manifest = small_registry
    monkeypatch.setattr(preflight, "_probe", lambda *_: (None, "version check failed (exit 1)"))
    assert checks_ok(environment_checks(cfg, frontend=False))
    required = environment_checks(cfg, frontend=False, require_blender=True)
    assert not checks_ok(required)
    assert next(check for check in required if check.name == "blender").detail.startswith("version check failed")


def test_starter_manifest_default_is_small_and_selected_pack_can_include_more_stages(small_registry):
    _cfg, manifest = small_registry
    assert starter_targets(manifest) == ["components/crate/v001"]
    assert starter_targets(manifest, ["crates", "crates"]) == ["components/crate/v001", "components/crate/v002"]
    with pytest.raises(ValueError, match="unknown pack"):
        starter_targets(manifest, ["missing"])
    data = yaml.safe_load(manifest.read_text())
    data["demo_refs"].append(data["demo_refs"][0])
    manifest.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="duplicate"):
        starter_targets(manifest)


def test_build_demo_list_validates_recipes_without_tools_or_index(small_registry, monkeypatch, capsys):
    cfg, manifest = small_registry
    monkeypatch.setattr(cli, "load_config", lambda: cfg)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("dry run must not launch tools or build")

    monkeypatch.setattr(cli, "environment_checks", forbidden)
    monkeypatch.setattr(cli, "_run_builds", forbidden)
    assert cli.main(["build-demo", "--manifest", str(manifest), "--pack", "crates", "--list"]) == 0
    assert "components/crate/v002" in capsys.readouterr().out
    assert not cfg.build_dir.exists() and not cfg.db_path.parent.exists()
    data = yaml.safe_load(manifest.read_text())
    data["demo_refs"] = ["components/missing/v001"]
    manifest.write_text(yaml.safe_dump(data))
    assert cli.main(["build-demo", "--manifest", str(manifest), "--list"]) == 1
    assert "components/missing/v001" in capsys.readouterr().err


def test_build_demo_stops_on_failed_preflight(small_registry, monkeypatch):
    cfg, manifest = small_registry
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "environment_checks", lambda *_args, **_kwargs: [Check("blender", False, True, "missing")])
    monkeypatch.setattr(cli, "_run_builds", lambda *_args, **_kwargs: pytest.fail("build must not start"))
    assert cli.main(["build-demo", "--manifest", str(manifest)]) == 1
    assert not cfg.db_path.exists()


@pytest.mark.parametrize("state, expected", [("ok", 0), ("failed", 1), ("invalid", 1), (None, 1)])
def test_cli_build_summary_requires_result_for_every_target_and_releases_resources(small_registry, monkeypatch, state, expected):
    cfg, _manifest = small_registry
    submitted = []
    released = []

    class FakeIndex:
        def __init__(self, _path):
            self.engine = SimpleNamespace(dispose=lambda: released.append("index"))

        def reindex(self, *_args):
            pass

    class FakeService:
        def __init__(self, _cfg, _store, _index, bus):
            self.bus = bus

        def start(self):
            pass

        async def stop(self):
            released.append("service")

        async def submit(self, kind, entity_id, vid, **_kwargs):
            submitted.append((kind, entity_id, vid))
            if state:
                self.bus.publish({"type": "build", "kind": kind, "id": entity_id, "vid": vid, "state": state})

        async def drain(self):
            pass

    monkeypatch.setattr(cli, "Index", FakeIndex)
    monkeypatch.setattr(cli, "BuildService", FakeService)
    assert cli._run_builds(cfg, [("materials", "toon", "v001"), ("components", "crate", "v001")], False) == expected
    assert submitted == [("components", "crate", "v001"), ("materials", "toon", "v001")]
    assert released == ["service", "index"]


def test_setup_uses_configured_registry_and_allows_browsing_without_blender(tmp_path):
    """Exercise the shell's set -e path without downloads or real tool processes."""
    project = tmp_path / "service"
    project.mkdir()
    shutil.copy2(Path(__file__).resolve().parents[1] / "run.sh", project / "run.sh")
    (project / "requirements.txt").write_text("# fixture\n")
    (project / "constraints.txt").write_text("# fixture\n")
    frontend = project / "frontend"
    frontend.mkdir()
    (frontend / "src").mkdir()
    for name in ("index.html", "vite.config.ts", "tsconfig.json", "package.json", "package-lock.json"):
        (frontend / name).write_text("fixture\n")
    (frontend / "dist").mkdir()
    (frontend / "dist/index.html").write_text("ready\n")
    configured_registry = project / "custom-registry"
    fake = project / ".venv/bin/python"
    fake.parent.mkdir(parents=True)
    fake.write_text("""#!/usr/bin/env bash
if [[ "${1:-}" == "--version" ]]; then
  echo 'Python 3.12.3'
elif [[ "${1:-}" == "-c" ]]; then
  case "$2" in
    *'print(load_config().registry_dir)'*) echo "$TEST_REGISTRY" ;;
    *'print(load_config().blender_bin)'*) echo "definitely-unavailable-blender-test" ;;
  esac
elif [[ "${1:-}" == "-m" && "${2:-}" == "registry" && "${3:-}" == "init" ]]; then
  mkdir -p "$TEST_REGISTRY"
  touch "$TEST_REGISTRY/palette.yaml" "$TEST_INIT_MARKER"
fi
exit 0
""")
    fake.chmod(0o755)
    bin_dir = project / "test-bin"
    bin_dir.mkdir()
    shutil.copy2(fake, bin_dir / "python3")
    marker = project / "init-called"
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", TEST_REGISTRY=str(configured_registry),
               TEST_INIT_MARKER=str(marker), NVM_DIR=str(project / "absent-nvm"))
    process = subprocess.run(["bash", str(project / "run.sh"), "--setup-only"], env=env,
                             capture_output=True, text=True, timeout=10)
    assert process.returncode == 0, process.stdout + process.stderr
    assert marker.is_file() and (configured_registry / "palette.yaml").is_file()
    assert "browsing works" in process.stderr
    assert "setup complete" in process.stdout


@pytest.mark.parametrize("report, has_model, should_build", [
    ({"status": "ok"}, True, False), ({"status": "ok"}, False, True),
    ({"status": "failed"}, True, True), ([], True, True), ("malformed", True, True),
])
def test_only_stale_repairs_failed_or_incomplete_artifacts(small_registry, monkeypatch, report, has_model, should_build):
    cfg, _manifest = small_registry
    planner = Planner(Store(cfg.registry_dir), cfg)
    for vid in ("v001", "v002"):
        digest = planner.resolve("components", "crate", vid).hash
        folder = cfg.build_dir / digest
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report.json").write_text(json.dumps(report) if report != "malformed" else "{")
        if has_model:
            (folder / "model.glb").write_bytes(b"fixture")
    calls = []

    def build(_cfg, targets, force):
        calls.append((targets, force))
        return 0

    monkeypatch.setattr(cli, "_run_builds", build)
    assert cli.cmd_build_all(cfg, SimpleNamespace(only_stale=True, force=False)) == 0
    assert bool(calls) is should_build
    if calls:
        assert calls[0][1] is True
        assert len(calls[0][0]) == 2
