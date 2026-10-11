"""Legacy catalog: read-only snapshots of models made before the registry.

Sources (config.yaml `legacy.sources`) are scanned for .blend/.fbx/.glb/.gltf/.obj files; a .blend
and an .fbx with the same name in one folder are one item (the .blend is rendered). Each item is
rendered by headless Blender (builder/legacy_build.py) into build/legacy/<hash>/ — previews,
model.glb for the web viewer and report.json. The hash is the file content hash, so unchanged
files are never re-rendered; the sources themselves are never modified.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .builds import EventBus
from .config import ROOT, Config
from builder.projection_views import PREVIEW_FILES, PREVIEW_NAMES

LEGACY_BUILDER = ROOT / "builder" / "legacy_build.py"
LEGACY_VERSION = 1          # bump when legacy_build.py output changes → everything re-renders
FORMATS = {".blend": "blend", ".fbx": "fbx", ".glb": "gltf", ".gltf": "gltf", ".obj": "obj"}
PRIORITY = ("blend", "fbx", "gltf", "obj")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "build"}
ARTIFACTS = ("model.glb", *PREVIEW_FILES, "report.json", "build.log")


@dataclass
class LegacyItem:
    id: str
    source: str
    folder: str
    name: str
    files: dict[str, str]           # format → absolute path
    size: int
    mtime: float
    hash: str = ""

    @property
    def format(self) -> str:
        return next(f for f in PRIORITY if f in self.files)

    @property
    def path(self) -> str:
        return self.files[self.format]

    def rel(self, root: Path) -> str:
        return str(Path(self.path).relative_to(root))


@dataclass
class _Job:
    item: LegacyItem
    state: str = "queued"


def _is_blend(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            head = f.read(7)
    except OSError:
        return False
    return head == b"BLENDER" or head[:4] == b"\x28\xb5\x2f\xfd" or head[:2] == b"\x1f\x8b"


def _format_of(path: Path) -> str | None:
    if path.suffix.lower() in FORMATS:
        return FORMATS[path.suffix.lower()]
    if path.suffix == "" and _is_blend(path):
        return "blend"
    return None


class LegacyService:
    def __init__(self, cfg: Config, bus: EventBus | None = None):
        self.cfg = cfg
        self.bus = bus or EventBus()
        self.out_root = cfg.build_dir / "legacy"
        self.cache_path = cfg.db_path.parent / "legacy_hashes.json"
        self.jobs: dict[str, _Job] = {}
        self._queue: asyncio.Queue[str] | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._items: dict[str, LegacyItem] = {}
        self._scanned = 0.0

    # ------------------------------------------------------------------ scan
    def sources(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "label": s.label, "path": str(s.path), "exists": s.path.is_dir()}
                for s in self.cfg.legacy.sources]

    def scan(self, *, max_age: float = 5.0) -> list[LegacyItem]:
        if time.monotonic() - self._scanned < max_age and self._items:
            return list(self._items.values())
        cache = self._load_cache()
        items: dict[str, LegacyItem] = {}
        for src in self.cfg.legacy.sources:
            if not src.path.is_dir():
                continue
            groups: dict[tuple[str, str], dict[str, Path]] = {}
            for path in sorted(src.path.rglob("*")):
                if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(src.path).parts):
                    continue
                fmt = _format_of(path)
                if fmt is None:
                    continue
                rel_dir = str(path.parent.relative_to(src.path))
                # a .blend and an .fbx export with the same name are one item; an extension-less
                # .blend is kept separate (it may coexist with name.blend and differ from it)
                stem = path.stem if path.suffix.lower() in FORMATS else f"{path.name} (без расширения)"
                groups.setdefault((rel_dir, stem), {}).setdefault(fmt, path)
            for (folder, stem), files in groups.items():
                item_id = hashlib.sha1(f"{src.name}/{folder}/{stem}".encode()).hexdigest()[:12]
                primary = next(files[f] for f in PRIORITY if f in files)
                st = primary.stat()
                item = LegacyItem(item_id, src.name, "" if folder == "." else folder, stem,
                                  {f: str(p) for f, p in files.items()}, st.st_size, st.st_mtime)
                item.hash = self._file_hash(primary, st, cache)
                items[item_id] = item
        self._save_cache(cache)
        self._items = items
        self._scanned = time.monotonic()
        return list(items.values())

    def item(self, item_id: str) -> LegacyItem | None:
        self.scan()
        return self._items.get(item_id)

    def _file_hash(self, path: Path, st: Any, cache: dict[str, Any]) -> str:
        key = str(path)
        hit = cache.get(key)
        if hit and hit["mtime"] == st.st_mtime and hit["size"] == st.st_size:
            return hit["hash"]
        digest = hashlib.sha256(f"legacy-v{LEGACY_VERSION}\n".encode())
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        value = digest.hexdigest()[:16]
        cache[key] = {"mtime": st.st_mtime, "size": st.st_size, "hash": value}
        return value

    def _load_cache(self) -> dict[str, Any]:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if data.get("_version") == LEGACY_VERSION else {"_version": LEGACY_VERSION}
        except (OSError, ValueError):
            return {"_version": LEGACY_VERSION}

    def _save_cache(self, cache: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(cache), encoding="utf-8")

    # ------------------------------------------------------------------ state
    def artifact_dir(self, digest: str) -> Path:
        return self.out_root / digest

    def report(self, digest: str) -> dict[str, Any] | None:
        try:
            return json.loads((self.artifact_dir(digest) / "report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def state(self, item: LegacyItem) -> str:
        job = self.jobs.get(item.hash)
        if job:
            return job.state
        report = self.report(item.hash)
        if report is None:
            return "none"
        return "ok" if report.get("status") == "ok" else "failed"

    def summary(self, item: LegacyItem, *, full: bool = False) -> dict[str, Any]:
        report = self.report(item.hash) or {}
        state = self.state(item)
        base = f"/api/legacy/files/{item.hash}"
        bust = f"?v={report.get('built_at', '').replace(':', '').replace('-', '')}"
        has = lambda name: (self.artifact_dir(item.hash) / name).is_file()  # noqa: E731
        stats = report.get("stats") or {}
        src = next((s for s in self.cfg.legacy.sources if s.name == item.source), None)
        data: dict[str, Any] = {
            "id": item.id, "source": item.source, "folder": item.folder, "name": item.name,
            "format": item.format, "formats": sorted(item.files, key=PRIORITY.index),
            "path": item.rel(src.path.parent) if src else item.path,
            "size": item.size, "mtime": datetime.fromtimestamp(item.mtime, timezone.utc).isoformat(timespec="seconds"),
            "hash": item.hash, "state": state, "error": report.get("error"),
            "preview": f"{base}/preview_iso.png{bust}" if has("preview_iso.png") else None,
            "model": f"{base}/model.glb{bust}" if has("model.glb") else None,
            "objects": stats.get("objects"), "tris": stats.get("tris"), "animated": bool(stats.get("actions")),
        }
        if full:
            data["report"] = report or None
            data["files"] = {f: str(Path(p)) for f, p in item.files.items()}
            data["urls"] = {k: f"{base}/{k}.png{bust}" for k in (f"preview_{name}" for name in PREVIEW_NAMES)
                            if has(f"{k}.png")}
            data["log"] = f"{base}/build.log" if has("build.log") else None
        return data

    # ------------------------------------------------------------------ builds
    def start(self) -> None:
        if self._workers:
            return
        self._queue = asyncio.Queue()
        self._workers = [asyncio.create_task(self._worker()) for _ in range(max(1, self.cfg.legacy.parallel))]

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

    async def submit(self, item: LegacyItem, *, force: bool = False) -> str:
        if item.hash in self.jobs:
            return self.jobs[item.hash].state
        if not force and self.report(item.hash) is not None:
            return self.state(item)
        assert self._queue is not None, "LegacyService.start() was not called"
        self.jobs[item.hash] = _Job(item)
        await self._queue.put(item.hash)
        self.bus.publish({"type": "legacy", "item": item.id, "state": "queued"})
        return "queued"

    def stale(self) -> list[LegacyItem]:
        return [i for i in self.scan(max_age=0) if self.report(i.hash) is None and i.hash not in self.jobs]

    async def _worker(self) -> None:
        assert self._queue is not None
        while True:
            digest = await self._queue.get()
            job = self.jobs.get(digest)
            try:
                if job is not None:
                    await self._run(job)
            except Exception as exc:  # keep the worker alive
                self.bus.publish({"type": "legacy", "item": job.item.id if job else None, "state": "failed",
                                  "error": repr(exc)})
            finally:
                self.jobs.pop(digest, None)
                self._queue.task_done()

    async def _run(self, job: _Job) -> None:
        item = job.item
        job.state = "running"
        self.bus.publish({"type": "legacy", "item": item.id, "state": "running"})
        final = self.artifact_dir(item.hash)
        tmp = self.out_root / f".{item.hash}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        cmd = [self.cfg.blender_bin, "-b", "--factory-startup"]
        if item.format == "blend":
            cmd.append(item.path)
        cmd += ["--python-exit-code", "1", "-P", str(LEGACY_BUILDER), "--",
                "--source", item.path, "--format", item.format, "--out", str(tmp),
                "--size", str(self.cfg.preview_size)]
        started = time.monotonic()
        error = None
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT)
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=self.cfg.build_timeout)
            except TimeoutError:
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                out, _ = await proc.communicate()
                error = f"timeout after {self.cfg.build_timeout}s"
            except asyncio.CancelledError:
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                await proc.communicate()
                raise
            code = proc.returncode
        except OSError as exc:
            out, code, error = b"", None, f"cannot start Blender: {exc}"
        text = out.decode(errors="replace")
        (tmp / "build.log").write_text(f"$ {' '.join(cmd)}\n\n{text}", encoding="utf-8")
        try:
            report = json.loads((tmp / "report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report = {"status": "failed", "error": error or f"Blender exited with code {code}"}
        if error:
            report.update(status="failed", error=error)
        if report.get("status") != "ok":
            report["log_tail"] = text.strip().splitlines()[-30:]
        report.update(built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      duration_s=round(time.monotonic() - started, 2), item=item.id)
        (tmp / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(final, ignore_errors=True)
        tmp.rename(final)
        self.bus.publish({"type": "legacy", "item": item.id, "state": "ok" if report["status"] == "ok" else "failed",
                          "error": report.get("error")})


def stats(service: LegacyService) -> dict[str, Any]:
    items = service.scan()
    counts: dict[str, int] = {}
    for item in items:
        state = service.state(item)
        counts[state] = counts.get(state, 0) + 1
    return {"items": len(items), "states": counts}
