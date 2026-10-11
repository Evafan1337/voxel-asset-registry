"""Build failures remain observable and do not stop subsequent queue jobs."""

import asyncio
import json
from pathlib import Path

import pytest

from backend.builds import BuildService, EventBus
from backend.config import Config, Legacy
from backend.index import Index, build_row_from_report
from backend.planner import Planner
from backend.store import Store


def service(tmp_path: Path) -> BuildService:
    root = tmp_path / "registry"
    entity = root / "components" / "test_box"
    (entity / "variants").mkdir(parents=True)
    (root / "palette.yaml").write_text("gray: '#888888'\n")
    (entity / "_base.md").write_text("---\nid: test_box\nparams:\n  width: {type: float, default: 1.0, min: 0.1, max: 1.0}\ninterface:\n  grid_size: [4, 4, 4]\n---\nTest box\n")
    (entity / "generator.py").write_text("def build(params):\n    return None\n")
    for n, width in ((1, 1.0), (2, 0.5)):
        (entity / "variants" / f"v{n:03}.yaml").write_text(
            f"id: v{n:03}\nparent: null\ndelta: {{width: {width}}}\nlevel: 1\nauthor: llm\nstatus: draft\n")
    cfg = Config(registry_dir=root, build_dir=tmp_path / "build",
                 db_path=tmp_path / "index.sqlite", legacy=Legacy(sources=[]))
    store = Store(root)
    index = Index(cfg.db_path)
    index.reindex(Planner(store, cfg), cfg.build_dir)
    return BuildService(cfg, store, index, EventBus())


def test_listener_failure_does_not_interrupt_other_subscribers(caplog):
    bus = EventBus()
    queue = bus.subscribe()
    received = []

    def broken(event):
        raise RuntimeError("subscriber unavailable")

    bus.listen(broken)
    bus.listen(received.append)
    bus.publish({"type": "build", "state": "failed"})
    assert queue.get_nowait()["state"] == "failed"
    assert received[0]["state"] == "failed"
    assert "Build event listener failed" in caplog.text


def test_unexpected_worker_failure_is_persisted_and_queue_keeps_running(tmp_path, monkeypatch):
    async def run():
        builds = service(tmp_path)
        seen = []

        async def fail(job):
            seen.append(job.plan.vid)
            raise RuntimeError("simulated export failure")

        monkeypatch.setattr(builds, "_run", fail)
        builds.start()
        try:
            results = [await builds.submit("components", "test_box", f"v{n:03}") for n in (1, 2)]
            await asyncio.wait_for(builds.drain(), 3)
            assert seen == ["v001", "v002"]
            for n, result in enumerate(results, 1):
                assert builds.state_of(result.hash) == "failed"
                assert builds.read_report(result.hash)["error"] == "simulated export failure"
                assert builds.store.variant("components", "test_box", f"v{n:03}").status == "failed"
                assert builds.index.builds([result.hash])[result.hash].state == "failed"
            assert builds.jobs == {}
        finally:
            await builds.stop()
            builds.index.engine.dispose()

    asyncio.run(run())


@pytest.mark.parametrize("payload", [[], None, "invalid", 1])
def test_non_object_report_does_not_break_catalog_or_index(tmp_path, payload):
    builds = service(tmp_path)
    digest = "1234567890abcdef"
    folder = builds.build_path(digest)
    folder.mkdir(parents=True)
    path = folder / "report.json"
    path.write_text(json.dumps(payload))
    try:
        assert builds.read_report(digest) is None
        assert build_row_from_report(path) is None
    finally:
        builds.index.engine.dispose()


@pytest.mark.parametrize("cached_status,artifact", [("failed", False), ("ok", False), ("ok", True)])
def test_explicit_build_retries_failed_or_incomplete_cache(tmp_path, cached_status, artifact):
    async def run():
        builds = service(tmp_path)
        plan = Planner(builds.store, builds.cfg).plan("components", "test_box", "v001")
        folder = builds.build_path(plan.hash)
        folder.mkdir(parents=True)
        (folder / "report.json").write_text(json.dumps({"status": cached_status}))
        if artifact:
            (folder / "model.glb").write_bytes(b"test cached artifact")
        # Set up a queue without workers so the scheduling result is deterministic.
        builds._queue = asyncio.Queue()
        try:
            result = await builds.submit("components", "test_box", "v001")
            expected = "ok" if cached_status == "ok" and artifact else "queued"
            assert result.state == expected
            assert (plan.hash in builds.jobs) == (expected == "queued")
        finally:
            await builds.stop()
            builds.index.engine.dispose()

    asyncio.run(run())
