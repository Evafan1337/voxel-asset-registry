"""Catalog-group component sheets: read-only manifests and explicit build/export actions."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import re
import struct
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any

from builder.zfight import read_glb
from builder.projection_views import PREVIEW_FILES, PREVIEW_NAMES

from .builds import BuildService
from .config import ROOT, Config
from .manual import BlenderLaunchError, BlenderSessions
from .planner import AssetResolution, Planner
from .resolve import RecipeError, build_hash
from .store import Store, check_id

EXPORT_SCRIPT = ROOT / "builder" / "blockout_sheet.py"
HASH_RE = re.compile(r"^[0-9a-f]{16}$")
SNAP_GRID = 0.25
GAP = 0.5


class BlockoutWorkbench:
    def __init__(self, cfg: Config, store: Store, builds: BuildService, sessions: BlenderSessions):
        self.cfg, self.store, self.builds, self.sessions = cfg, store, builds, sessions
        self._bounds_cache: OrderedDict[tuple[str, int, int], dict[str, list[float]] | None] = OrderedDict()
        self._export_locks: dict[str, asyncio.Lock] = {}
        self._export_semaphore = asyncio.Semaphore(max(1, cfg.parallel_builds))

    @property
    def root(self) -> Path:
        return self.cfg.db_path.parent / "blockout-sheets"

    @staticmethod
    def _latest(p: Planner, kind: str, eid: str) -> str:
        variants = [v for v in p.variants(kind, eid).values() if v.status != "archived"]
        if not variants:
            raise RecipeError(f"{kind}/{eid}: no non-archived variants")
        return max(variants, key=lambda v: (v.status == "approved",
                   int(v.id[1:]) if v.id[1:].isdigit() else -1, v.id)).id

    def _context(self, p: Planner, asset: str | None, vid: str | None
                 ) -> tuple[dict[str, Any] | None, dict[str, dict[str, list[str]]]]:
        if asset is None:
            if vid is not None:
                raise RecipeError("v requires an asset context")
            return None, {}
        check_id(asset)
        if not self.store.has_entity("assets", asset):
            raise FileNotFoundError(f"assets/{asset}")
        vid = check_id(vid) if vid is not None else self._latest(p, "assets", asset)
        res = p.resolve_asset(asset, vid)
        refs: dict[str, dict[str, list[str]]] = {}

        def walk(current: AssetResolution, prefix: str = "") -> None:
            for slot in current.slots.values():
                child = slot.component
                if child is None:
                    continue
                path = f"{prefix}{slot.name}"
                if isinstance(child, AssetResolution):
                    walk(child, path + ".")
                else:
                    refs.setdefault(child.entity.id, {}).setdefault(child.variant.id, []).append(path)

        walk(res)
        return {"id": asset, "vid": vid, "ref": f"assets/{asset}/{vid}", "hash": res.hash}, refs

    def discovery(self, asset: str, vid: str | None = None) -> dict[str, Any]:
        with self.store.write_lock:
            context, refs = self._context(Planner(self.store, self.cfg), asset, vid)
            groups = []
            for group in self.store.catalog_groups():
                components = {ref.partition("/")[2] for ref in group.get("items", [])
                              if ref.startswith("components/")}
                if components & refs.keys():
                    groups.append({"id": group["id"], "title": group["title"], "component_count": len(components)})
            if not groups:
                groups = [{"id": f"asset:{asset}", "title": self.store.resolve("assets", asset).title,
                           "component_count": sum(len(variants) for variants in refs.values())}]
            return {"groups": groups, "context": context}

    def _glb_bounds(self, path: Path) -> dict[str, list[float]] | None:
        try:
            stat = path.stat()
        except OSError:
            return None  # A rebuild may replace the artifact directory between checks.
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if key in self._bounds_cache:
            self._bounds_cache.move_to_end(key)
            return self._bounds_cache[key]
        bbox = None
        try:
            triangles = read_glb(path)
            if triangles:
                low = [min(point[i] for tri in triangles for point in (tri.a, tri.b, tri.c)) for i in range(3)]
                high = [max(point[i] for tri in triangles for point in (tri.a, tri.b, tri.c)) for i in range(3)]
                if all(math.isfinite(v) for v in low + high):
                    bbox = {"min": low, "max": high}
        except (OSError, ValueError, KeyError, IndexError, TypeError, OverflowError, struct.error):
            pass
        self._bounds_cache[key] = bbox
        while len(self._bounds_cache) > 128:
            self._bounds_cache.popitem(last=False)
        return bbox

    @staticmethod
    def _layout(members: list[dict[str, Any]]) -> dict[str, Any]:
        columns = max(1, math.ceil(math.sqrt(len(members))))
        rows = math.ceil(len(members) / columns)
        widths = [0.0] * columns
        depths = [0.0] * rows
        for index, member in enumerate(members):
            widths[index % columns] = max(widths[index % columns], member["dimensions"][0])
            depths[index // columns] = max(depths[index // columns], member["dimensions"][2])
        sizes = [[math.ceil(value / SNAP_GRID) * SNAP_GRID + GAP for value in values]
                 for values in (widths, depths)]
        centers = [[sum(values[:i]) + value / 2 for i, value in enumerate(values)] for values in sizes]
        for index, member in enumerate(members):
            bbox = member["bbox"]
            x = round(centers[0][index % columns] / SNAP_GRID) * SNAP_GRID
            z = round(centers[1][index // columns] / SNAP_GRID) * SNAP_GRID
            member["position"] = [round(x - (bbox["min"][0] + bbox["max"][0]) / 2, 6),
                                  round(-bbox["min"][1], 6),
                                  round(z - (bbox["min"][2] + bbox["max"][2]) / 2, 6)]
        return {"columns": columns, "gap": GAP,
                "bounds": [sum(sizes[0]), max((m["dimensions"][1] for m in members), default=0), sum(sizes[1])]}

    def snapshot(self, group_id: str, asset: str | None = None, vid: str | None = None,
                 *, recipes: bool = False) -> dict[str, Any]:
        with self.store.write_lock:
            return self._snapshot(group_id, asset, vid, recipes=recipes)

    def _preview_urls(self, digest: str) -> dict[str, str]:
        return {f"preview_{name}": f"/api/blockout-sheets/files/{digest}/preview_{name}.png"
                for name in PREVIEW_NAMES if (self.root / digest / f"preview_{name}.png").is_file()}

    def _snapshot(self, group_id: str, asset: str | None, vid: str | None, *, recipes: bool) -> dict[str, Any]:
        p = Planner(self.store, self.cfg)
        fallback = group_id.startswith("asset:")
        if fallback:
            eid = check_id(group_id[len("asset:"):])
            if asset is not None and asset != eid:
                raise RecipeError("fallback sheet id must match its asset context")
            asset = eid
        else:
            check_id(group_id)
        context, refs = self._context(p, asset, vid)
        if fallback:
            group = {"id": group_id, "title": p.entity("assets", asset).title,
                     "items": [f"components/{eid}" for eid in refs]}
        else:
            group = next((g for g in self.store.catalog_groups() if g.get("id") == group_id), None)
            if group is None:
                raise FileNotFoundError(f"catalog group '{group_id}'")
        members = []
        seen = set()
        component_ids = []
        for ref in group.get("items", []):
            kind, sep, eid = ref.partition("/")
            if kind != "components" or not sep or eid in seen:
                continue
            check_id(eid)
            seen.add(eid)
            component_ids.append(eid)
            selections = refs.get(eid)
            if selections is None:
                try:
                    selections = {self._latest(p, "components", eid): []}
                except RecipeError:
                    selections = {None: []}
            for selected, slots in selections.items():
                member: dict[str, Any] = {"id": eid, "title": eid, "label": eid, "vid": selected,
                    "ref": f"components/{eid}/{selected}" if selected else None, "hash": None, "model": None,
                    "url": None, "preview": None, "build_state": "invalid", "params": {},
                    "dimensions": [1.0, 1.0, 1.0], "bbox": {"min": [-.5, 0, -.5], "max": [.5, 1, .5]},
                    "source_slots": slots, "error": None}
                try:
                    doc = p.entity("components", eid)
                    member["title"] = member["label"] = doc.title
                    if selected is None:
                        raise RecipeError(f"components/{eid}: no non-archived variants")
                    plan = p.plan("components", eid, selected)
                    member["hash"], member["params"] = plan.hash, plan.resolution.params
                    report = self.builds.read_report(plan.hash)
                    job = self.builds.jobs.get(plan.hash)
                    member["build_state"] = job.state if job else (
                        "none" if report is None else "ok" if report.get("status") == "ok" else "failed")
                    folder = self.builds.build_path(plan.hash)
                    model = folder / "model.glb"
                    preview = folder / "preview_iso.png"
                    bust = re.sub(r"[^0-9]", "", (report or {}).get("built_at") or "")
                    base = f"/api/builds/{plan.hash}"
                    bbox = self._glb_bounds(model) if model.is_file() else None
                    if model.is_file():
                        member["model"] = member["url"] = f"{base}/model.glb?v={bust}"
                    if preview.is_file():
                        member["preview"] = f"{base}/preview_iso.png?v={bust}"
                    if bbox is None:
                        dimensions = (report or {}).get("stats", {}).get("bbox_m")
                        if (not isinstance(dimensions, list) or len(dimensions) != 3
                                or not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in dimensions)):
                            dimensions = [v * doc.interface.voxel_size for v in doc.interface.grid_size]
                        bbox = {"min": [-dimensions[0] / 2, 0, -dimensions[2] / 2],
                                "max": [dimensions[0] / 2, dimensions[1], dimensions[2] / 2]}
                    member["bbox"] = bbox
                    member["dimensions"] = [bbox["max"][i] - bbox["min"][i] for i in range(3)]
                    if recipes:
                        member["recipe"] = plan.recipe
                except RecipeError as exc:
                    member["error"] = str(exc)
                members.append(member)
        related = []
        for eid in self.store.entity_ids("assets"):
            try:
                doc = p.entity("assets", eid)
                if doc.abstract:
                    continue
                _ctx, used = self._context(p, eid, self._latest(p, "assets", eid))
                if set(component_ids) & used.keys() or f"assets/{eid}" in group.get("items", []):
                    related.append({"id": eid, "title": doc.title})
            except (RecipeError, FileNotFoundError):
                continue
        layout = self._layout(members)
        signature = {"group_id": group_id, "title": group["title"], "context": context,
                     "members": [{k: m[k] for k in ("id", "title", "vid", "hash", "dimensions", "bbox", "position")}
                                 for m in members], "layout": layout}
        digest = build_hash("blockout-sheet-v1", signature)
        available = (self.root / digest / "sheet.blend").is_file()
        return {"version": 1, "id": group_id, "group_id": group_id, "title": group["title"], "hash": digest,
                "snap_grid": SNAP_GRID, "layout": layout, "members": members, "related_assets": related,
                "context": context, "previews": self._preview_urls(digest), "blend": {"available": available,
                    "url": f"/api/blockout-sheets/files/{digest}/sheet.blend" if available else None}}

    async def build_missing(self, group_id: str, asset: str | None = None, vid: str | None = None) -> dict[str, Any]:
        sheet = self.snapshot(group_id, asset, vid)
        submitted = []
        for member in sheet["members"]:
            if member["hash"] is None or member["model"] is not None:
                continue
            result = await self.builds.submit("components", member["id"], member["vid"],
                                              force=self.builds.read_report(member["hash"]) is not None)
            submitted.append({"ref": member["ref"], **result.__dict__})
        return {"sheet": self.snapshot(group_id, asset, vid), "submitted": submitted}

    def file(self, digest: str, name: str) -> Path:
        if not HASH_RE.fullmatch(digest) or name not in ("sheet.blend", *PREVIEW_FILES):
            raise FileNotFoundError(name)
        path = self.root / digest / name
        if not path.is_file() or not path.resolve().is_relative_to(self.root.resolve()):
            raise FileNotFoundError(name)
        return path

    async def _generate(self, manifest: dict[str, Any], dest: Path, *, previews_only: bool = False) -> None:
        manifest_path = dest.parent / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [self.cfg.blender_bin, "-b", "-noaudio", "--factory-startup", "--python-exit-code", "1", "-P", str(EXPORT_SCRIPT),
               "--", "--manifest", str(manifest_path), "--out", str(dest), "--preview", str(dest.parent)]
        if previews_only:
            cmd.append("--previews-only")
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT)
        except OSError as exc:
            raise BlenderLaunchError(f"cannot start Blender ({self.cfg.blender_bin}): {exc}") from exc
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), timeout=self.cfg.build_timeout)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await proc.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise BlenderLaunchError(f"sheet export timed out after {self.cfg.build_timeout}s") from None
        (dest.parent / "export.log").write_bytes(output)
        if (proc.returncode != 0 or not all((dest.parent / name).is_file() for name in PREVIEW_FILES)
                or not previews_only and not dest.is_file()):
            tail = "\n".join(output.decode(errors="replace").strip().splitlines()[-15:])
            raise BlenderLaunchError(f"Blender could not export sheet (exit {proc.returncode}):\n{tail}")

    async def blender(self, group_id: str, asset: str | None = None, vid: str | None = None,
                      *, open_gui: bool = True) -> dict[str, Any]:
        manifest = self.snapshot(group_id, asset, vid, recipes=True)
        if not manifest["members"] or any(m["error"] for m in manifest["members"]):
            raise RecipeError("sheet has no components or contains invalid component recipes")
        digest = manifest["hash"]
        lock = self._export_locks.setdefault(digest, asyncio.Lock())
        async with lock:
            folder = self.root / digest
            blend = folder / "sheet.blend"
            needs_blend = not blend.is_file()
            if needs_blend or len(self._preview_urls(digest)) != len(PREVIEW_NAMES):
                self.root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=f".{digest}-", dir=self.root) as tmp:
                    staging = Path(tmp)
                    async with self._export_semaphore:
                        if needs_blend:
                            await self._generate(manifest, staging / "sheet.blend")
                        else:
                            await self._generate(manifest, staging / "sheet.blend", previews_only=True)
                    folder.mkdir(parents=True, exist_ok=True)
                    for name in ("export.log", *PREVIEW_FILES, *(("manifest.json", "sheet.blend") if needs_blend else ())):
                        path = staging / name
                        if path.exists():
                            path.replace(folder / name)
        session = None
        if open_gui:
            try:
                session = await self.sessions.open(blend, [], session_script=None)
            except BlenderLaunchError as exc:
                session = {"state": "error", "error": str(exc)}
        sheet = copy.deepcopy(manifest)
        for member in sheet["members"]:
            member.pop("recipe", None)
        sheet["blend"] = {"available": True, "url": f"/api/blockout-sheets/files/{digest}/sheet.blend"}
        sheet["previews"] = self._preview_urls(digest)
        return {"sheet": sheet, "blend": {"url": sheet["blend"]["url"], "file": str(blend)}, "blender": session}
