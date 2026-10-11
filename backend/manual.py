"""Manual geometry variants: hand-edited .blend files that replace a component's generator or
an asset's slot assembly.

A fork writes `variants/<vid>.blend` and a child variant with `source: <vid>.blend`:
- from a procedural variant, headless Blender builds it and saves the scene
  (`builder/build.py --save-blend`), with sockets, semantic labels and animation intact;
  an asset keeps one object tree per slot, parented to the slot it stands on;
- from a manual variant, its .blend is copied.
Then the Blender GUI opens the file with builder/blender_session.py, a sidebar panel for
palette colors, socket status and "save and build". The server must run in the user's
graphical session because the GUI is its child process.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .config import BUILDER_SCRIPT, ROOT, Config
from .models import Kind, variant_model
from .planner import Planner
from .resolve import RecipeError
from .store import now_iso

SESSION_SCRIPT = ROOT / "builder" / "blender_session.py"
STARTUP_GRACE_S = 1.5  # a GUI that dies this fast (no display, bad file) is reported as an error


class BlenderLaunchError(Exception):
    """Blender could not be started or quit immediately; the message is shown in the UI."""


async def seed_blend(cfg: Config, recipe: dict[str, Any], dest: Path) -> None:
    """Run the generator in headless Blender and save the component to `dest` (a new file;
    the recipe and the throwaway report go next to it)."""
    recipe_path = dest.with_suffix(".recipe.json")
    recipe_path.write_text(json.dumps(recipe, ensure_ascii=False), encoding="utf-8")
    cmd = [cfg.blender_bin, "-b", "--factory-startup", "--python-exit-code", "1",
           "-P", str(BUILDER_SCRIPT), "--", "--recipe", str(recipe_path), "--out", str(dest.parent),
           "--save-blend", str(dest)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except OSError as exc:
        raise BlenderLaunchError(f"cannot start Blender ({cfg.blender_bin}): {exc}") from exc
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=cfg.build_timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise BlenderLaunchError(f"seeding .blend timed out after {cfg.build_timeout}s") from None
    if proc.returncode != 0 or not dest.is_file():
        tail = "\n".join(out.decode(errors="replace").strip().splitlines()[-15:])
        raise BlenderLaunchError(f"Blender could not save the .blend (exit {proc.returncode}):\n{tail}")


async def fork(cfg: Config, planner: Planner, kind: Kind, entity_id: str, parent: str, *, note: str = "",
               tags: list[str] | None = None) -> str:
    """Create the manual child of `parent` (a component or a whole asset composition) and its
    .blend; returns the new variant id."""
    if kind not in ("components", "assets"):
        raise RecipeError(f"{kind} cannot be edited in Blender")
    store = planner.store
    res = planner.resolve(kind, entity_id, parent)
    folder = store.entity_dir(kind, entity_id) / "variants"
    with tempfile.TemporaryDirectory(prefix=".fork-", dir=folder) as tmp:
        seed = Path(tmp) / "seed.blend"
        if res.source is not None:
            shutil.copyfile(res.source.path, seed)
        else:
            await seed_blend(cfg, planner.plan(kind, entity_id, parent).recipe, seed)
        vid = store.next_vid(kind, entity_id)
        blend = store.source_path(kind, entity_id, f"{vid}.blend")
        seed.replace(blend)

    variant = variant_model(kind)(
        id=vid, parent=parent, source=blend.name, level=res.variant.level, author="human",
        note=note or f"Ручная правка {parent} в Blender", tags=tags if tags is not None else ["manual"],
        status="draft", created=now_iso())
    path = store.save_variant(kind, entity_id, variant)
    planner.forget_variants(kind, entity_id)
    try:
        planner.resolve(kind, entity_id, vid)
    except RecipeError:
        path.unlink(missing_ok=True)
        blend.unlink(missing_ok=True)
        raise
    return vid


def _has_display() -> bool:
    if sys.platform != "linux":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


class BlenderSessions:
    """GUI Blender processes started by the server, one per .blend file."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._procs: dict[Path, subprocess.Popen[bytes]] = {}

    def is_open(self, path: Path) -> bool:
        proc = self._procs.get(path)
        return proc is not None and proc.poll() is None

    async def open(self, path: Path, session_args: list[str], *,
                   session_script: Path | None = SESSION_SCRIPT) -> dict[str, Any]:
        for known, proc in list(self._procs.items()):  # reap closed windows
            if proc.poll() is not None:
                del self._procs[known]
        if path in self._procs:
            return {"state": "already_open", "pid": self._procs[path].pid, "file": str(path)}
        if not _has_display():
            raise BlenderLaunchError("сервер запущен без графической сессии (нет DISPLAY / WAYLAND_DISPLAY): "
                                     "запустите ./run.sh из терминала рабочего стола")
        log_dir = self.cfg.db_path.parent / "blender"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_owner = path.parent.parent.name if session_script is not None else path.parent.name
        log_path = log_dir / f"{log_owner}-{path.stem}.log"
        cmd = [self.cfg.blender_bin, str(path)]
        if session_script is not None:
            cmd.extend(["--python", str(session_script), "--", *session_args])
        with log_path.open("wb") as log:
            try:
                proc = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                raise BlenderLaunchError(f"cannot start Blender ({self.cfg.blender_bin}): {exc}") from exc
        await asyncio.sleep(STARTUP_GRACE_S)
        if proc.poll() is not None:
            tail = "\n".join(log_path.read_text(errors="replace").strip().splitlines()[-15:])
            raise BlenderLaunchError(f"Blender завершился сразу (код {proc.returncode}):\n{tail}")
        self._procs[path] = proc
        return {"state": "opened", "pid": proc.pid, "file": str(path), "log": str(log_path)}
