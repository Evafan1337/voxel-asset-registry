"""In-process build queue: asyncio workers that run headless Blender as a subprocess."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import BUILDER_SCRIPT, ROOT, Config
from .index import Index
from .models import Kind
from .planner import Plan, Planner
from .resolve import RecipeError
from .store import Store, now_iso
from builder.projection_views import PREVIEW_FILES

ARTIFACTS = ("model.glb", *PREVIEW_FILES, "report.json",
             "preview_34.png", "preview_side.png", "preview_back.png", "preview_pose.png",
             "build.log", "recipe.json")

Target = tuple[Kind, str, str]  # (kind, entity_id, vid)
Listener = Callable[[dict[str, Any]], None]
logger = logging.getLogger(__name__)


class EventBus:
    """Fan-out of build events to SSE subscribers and plain callbacks (CLI)."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()
        self._listeners: list[Listener] = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._queues.discard(queue)

    def listen(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def publish(self, event: dict[str, Any]) -> None:
        event = {"ts": now_iso(), **event}
        for queue in list(self._queues):
            if not queue.full():
                queue.put_nowait(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Build event listener failed")


@dataclass
class Job:
    plan: Plan
    force: bool
    targets: set[Target] = field(default_factory=set)
    state: str = "queued"  # queued | running


@dataclass
class SubmitResult:
    hash: str | None
    state: str  # queued | running | ok | failed | invalid
    error: str | None = None


class BuildService:
    def __init__(self, cfg: Config, store: Store, index: Index, bus: EventBus):
        self.cfg = cfg
        self.store = store
        self.index = index
        self.bus = bus
        self.jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] | None = None
        self._workers: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._workers:
            return
        self._queue = asyncio.Queue()
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(max(1, self.cfg.parallel_builds))]

    async def stop(self) -> None:
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        self.jobs.clear()
        if self._queue is not None:
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()
        self._queue = None

    async def drain(self) -> None:
        if self._queue is not None:
            await self._queue.join()

    # ------------------------------------------------------------------ state
    def build_path(self, digest: str) -> Path:
        return self.cfg.build_dir / digest

    def read_report(self, digest: str) -> dict[str, Any] | None:
        path = self.build_path(digest) / "report.json"
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            return report if isinstance(report, dict) else None
        except (OSError, ValueError):
            return None

    def state_of(self, digest: str | None) -> str:
        if not digest:
            return "none"
        job = self.jobs.get(digest)
        if job is not None:
            return job.state
        report = self.read_report(digest)
        if report is None:
            return "none"
        return "ok" if report.get("status") == "ok" else "failed"

    def queue_snapshot(self) -> list[dict[str, Any]]:
        return [{"hash": h, "state": j.state, "targets": ["/".join(t) for t in sorted(j.targets)]}
                for h, j in self.jobs.items()]

    # ------------------------------------------------------------------ submit
    async def submit(self, kind: Kind, entity_id: str, vid: str, *, force: bool = False) -> SubmitResult:
        planner = Planner(self.store, self.cfg)
        target: Target = (kind, entity_id, vid)
        try:
            plan = planner.plan(kind, entity_id, vid)
        except RecipeError as exc:
            self._set_status([target], ok=False)
            self.bus.publish({"type": "variant", "kind": kind, "id": entity_id, "vid": vid,
                              "state": "invalid", "error": str(exc)})
            return SubmitResult(None, "invalid", str(exc))

        job = self.jobs.get(plan.hash)
        if job is not None:
            job.targets.add(target)
            return SubmitResult(plan.hash, job.state)

        report = None if force else self.read_report(plan.hash)
        required_artifact = "preview_iso.png" if kind == "materials" else "model.glb"
        if (report is not None and report.get("status") == "ok"
                and (self.build_path(plan.hash) / required_artifact).is_file()):
            ok = report.get("status") == "ok"
            self._set_status([target], ok=ok)
            self._publish_done(plan.hash, [target], ok, cached=True)
            return SubmitResult(plan.hash, "ok" if ok else "failed")

        if self._queue is None:
            raise RuntimeError("BuildService.start() was not called")
        self.jobs[plan.hash] = Job(plan, force, {target})
        await self._queue.put(plan.hash)
        self.bus.publish({"type": "build", "hash": plan.hash, "state": "queued", "kind": kind, "id": entity_id,
                          "vid": vid})
        return SubmitResult(plan.hash, "queued")

    # ------------------------------------------------------------------ worker
    async def _worker(self, _n: int) -> None:
        assert self._queue is not None
        while True:
            digest = await self._queue.get()
            job = self.jobs.get(digest)
            try:
                if job is not None:
                    await self._run(job)
            except Exception as exc:  # keep the worker alive whatever happens
                logger.exception("Build failed outside the Blender subprocess")
                if job is not None:
                    self._record_worker_failure(job, exc)
                else:
                    self.bus.publish({"type": "build", "hash": digest, "state": "failed", "error": str(exc)})
            finally:
                self.jobs.pop(digest, None)
                self._queue.task_done()

    def _record_worker_failure(self, job: Job, exc: Exception) -> None:
        """Keep an unexpected worker failure visible after its queue entry is removed."""
        plan = job.plan
        report = {"status": "failed", "checks": [], "error": str(exc),
                  "hash": plan.hash, "kind": plan.kind, "id": plan.entity_id,
                  "variant": plan.vid, "built_at": now_iso()}
        try:
            final_dir = self.build_path(plan.hash)
            final_dir.mkdir(parents=True, exist_ok=True)
            report_path = final_dir / "report.json"
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            self.index.record_build(report_path)
            self._set_status(sorted(job.targets), ok=False)
        except Exception:
            logger.exception("Could not persist the failed build")
        self._publish_done(plan.hash, sorted(job.targets), False, cached=False, error=report["error"])

    async def _run(self, job: Job) -> None:
        plan = job.plan
        job.state = "running"
        self.bus.publish({"type": "build", "hash": plan.hash, "state": "running", "kind": plan.kind,
                          "id": plan.entity_id, "vid": plan.vid})
        final_dir = self.build_path(plan.hash)
        tmp_dir = self.cfg.build_dir / f".{plan.hash}.tmp"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True)
        recipe_path = tmp_dir / "recipe.json"
        recipe_path.write_text(json.dumps(plan.recipe, indent=2, ensure_ascii=False), encoding="utf-8")

        cmd = [self.cfg.blender_bin, "-b", "--factory-startup", "--python-exit-code", "1",
               "-P", str(BUILDER_SCRIPT), "--", "--recipe", str(recipe_path), "--out", str(tmp_dir)]
        started = time.monotonic()
        exit_code, output, error = await self._exec(cmd)
        duration = round(time.monotonic() - started, 2)

        log_text = f"$ {' '.join(cmd)}\n\n{output}"
        (tmp_dir / "build.log").write_text(log_text, encoding="utf-8")
        report = self._finalize_report(tmp_dir, plan, exit_code, error, duration, output)

        shutil.rmtree(final_dir, ignore_errors=True)
        tmp_dir.rename(final_dir)
        self.index.record_build(final_dir / "report.json")

        ok = report["status"] == "ok"
        targets = sorted(job.targets)
        self._set_status(targets, ok=ok)
        self._publish_done(plan.hash, targets, ok, cached=False, error=report.get("error"))

    async def _exec(self, cmd: list[str]) -> tuple[int | None, str, str | None]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        except OSError as exc:
            return None, "", f"cannot start Blender ({self.cfg.blender_bin}): {exc}"
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self.cfg.build_timeout)
        except TimeoutError:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            out, _ = await proc.communicate()
            return proc.returncode, out.decode(errors="replace"), f"timeout after {self.cfg.build_timeout}s"
        except asyncio.CancelledError:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await proc.communicate()
            raise
        return proc.returncode, out.decode(errors="replace"), None

    @staticmethod
    def _finalize_report(out_dir: Path, plan: Plan, exit_code: int | None, error: str | None,
                         duration: float, output: str) -> dict[str, Any]:
        path = out_dir / "report.json"
        try:
            report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report = {"status": "failed", "checks": [], "error": None}
        if not isinstance(report, dict):
            report = {"status": "failed", "checks": [], "error": "invalid Blender report"}
        if report.get("status") not in ("ok", "failed"):
            report["status"] = "failed"
            report["error"] = report.get("error") or "Blender did not produce a valid build status"
        if error:
            report["status"] = "failed"
            report["error"] = error
        elif exit_code != 0:
            report["status"] = "failed"
            report["error"] = report.get("error") or f"Blender exited with code {exit_code}"
        if plan.kind != "materials" and not (out_dir / "model.glb").is_file() and report.get("status") == "ok":
            report["status"] = "failed"
            report["error"] = "model.glb was not produced"
        report.update({
            "hash": plan.hash, "kind": plan.kind, "id": plan.entity_id, "variant": plan.vid,
            "exit_code": exit_code, "duration_s": duration, "built_at": now_iso(),
        })
        if report["status"] != "ok":
            report["log_tail"] = output.strip().splitlines()[-40:]
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    # ------------------------------------------------------------------ results
    def _set_status(self, targets: list[Target], *, ok: bool) -> None:
        """Mirror the build result into variant files (approved/archived are user decisions)."""
        planner = Planner(self.store, self.cfg)
        for kind, entity_id, vid in targets:
            with self.store.write_lock:
                self._set_target_status(planner, kind, entity_id, vid, ok=ok)

    def _set_target_status(self, planner: Planner, kind: Kind, entity_id: str, vid: str, *, ok: bool) -> None:
        try:
            variant = self.store.variant(kind, entity_id, vid)
        except (FileNotFoundError, RecipeError):
            return
        if variant.status in ("draft", "built", "failed"):
            new_status = "built" if ok else "failed"
            if variant.status != new_status:
                variant.status = new_status
                self.store.save_variant(kind, entity_id, variant)
        planner.forget_variants(kind, entity_id)
        self.index.upsert_variant(planner, kind, entity_id, variant)

    def _publish_done(self, digest: str, targets: list[Target], ok: bool, *, cached: bool,
                      error: str | None = None) -> None:
        for kind, entity_id, vid in targets:
            self.bus.publish({"type": "build", "hash": digest, "state": "ok" if ok else "failed",
                              "cached": cached, "kind": kind, "id": entity_id, "vid": vid, "error": error})
