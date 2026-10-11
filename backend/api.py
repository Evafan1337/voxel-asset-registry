"""FastAPI application: REST API, SSE build events and the built frontend."""

from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import frontmatter
from . import __version__
from .builds import ARTIFACTS, BuildService, EventBus
from .blockout_workbench import BlockoutWorkbench
from .config import FRONTEND_DIST, ROOT, Config, RegistrySettings, load_config, save_priority_tags
from .index import Index, VariantRow
from .models import (
    KINDS,
    AssetVariant,
    Author,
    ComponentVariant,
    Kind,
    SlotSpec,
    Socket,
    Status,
    Variant,
    variant_to_yaml_dict,
)
from .godot import godot_tres
from .legacy import ARTIFACTS as LEGACY_ARTIFACTS
from .legacy import LegacyService
from .legacy import stats as legacy_stats
from . import manual
from .manual import BlenderLaunchError, BlenderSessions
from .references import ReferenceLabError, ReferenceLab
from .planner import AssetResolution, ComponentResolution, Planner, Resolution
from .resolve import RecipeError, parse_entity_slot_ref
from .store import Store, check_id, now_iso
from .tags import EntityRef, TagCatalog
from builder.projection_views import PREVIEW_NAMES

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")
CHARACTER_PREVIEWS = ("preview_34", "preview_side", "preview_back", "preview_pose")
_MEDIA = {".glb": "model/gltf-binary", ".png": "image/png", ".json": "application/json", ".log": "text/plain",
          ".yaml": "text/plain"}


class NewVariant(BaseModel):
    parent: str | None = None
    delta: dict[str, Any] = {}
    slots: dict[str, str | None] = {}
    slot_offsets: dict[str, tuple[float, float, float]] = {}
    params_delta: dict[str, Any] = {}
    note: str = ""
    tags: list[str] = []
    level: int | None = Field(None, ge=0, le=3)
    author: Author = "human"
    build: bool = True


class NewAssetVariant(BaseModel):
    slots: dict[str, str | None]
    slot_offsets: dict[str, tuple[float, float, float]] = {}
    level: int = Field(1, ge=0, le=3)
    note: str = ""
    tags: list[str] = []
    author: Author = "human"


class NewAsset(BaseModel):
    id: str
    title: str
    description: str = ""
    grid_size: tuple[int, int, int]
    voxel_size: float = 0.25
    pivot: str = "bottom_center"
    sockets: list[Socket] = []
    slots: dict[str, SlotSpec]
    variant: NewAssetVariant
    tags: list[str] = []
    build: bool = True


class CatalogGroup(BaseModel):
    id: str
    title: str
    items: list[str] = []


class CatalogGroups(BaseModel):
    groups: list[CatalogGroup] = []


class VariantPatch(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    tags: list[str] | None = None
    status: Status | None = None
    note: str | None = None


class TagRename(BaseModel):
    name: str


class OpenInBlender(BaseModel):
    fork: bool = True   # False: continue editing the variant's own draft .blend
    note: str = ""


class OpenBlockoutSheet(BaseModel):
    open: bool = True


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    store = Store(cfg.registry_dir)
    settings_lock = store.write_lock
    index = Index(cfg.db_path)
    bus = EventBus()
    builds = BuildService(cfg, store, index, bus)
    legacy = LegacyService(cfg, bus)
    sessions = BlenderSessions(cfg)
    tags = TagCatalog(cfg, store, index)
    workbench = BlockoutWorkbench(cfg, store, builds, sessions)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            index.reindex(Planner(store, cfg), cfg.build_dir)
            builds.start()
            legacy.start()
            yield
        finally:
            try:
                await builds.stop()
            finally:
                try:
                    await legacy.stop()
                finally:
                    index.engine.dispose()

    app = FastAPI(title="Voxel Asset Registry", version=__version__, lifespan=lifespan)
    app.state.cfg, app.state.store, app.state.index, app.state.builds = cfg, store, index, builds
    app.state.workbench = workbench

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__,
                "registry_available": (cfg.registry_dir / "palette.yaml").is_file(),
                "frontend_available": (FRONTEND_DIST / "index.html").is_file()}

    @app.exception_handler(RecipeError)
    async def _recipe_error(_req: Request, exc: RecipeError) -> JSONResponse:
        return JSONResponse({"detail": "recipe error", "errors": exc.errors}, status_code=422)

    @app.exception_handler(FileNotFoundError)
    async def _not_found(_req: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)

    # ------------------------------------------------------------------ helpers
    def planner() -> Planner:
        return Planner(store, cfg)

    def urls(digest: str | None, *, report: dict[str, Any] | None = None) -> dict[str, str] | None:
        if not digest:
            return None
        if report is None:
            report = builds.read_report(digest)
        if report is None:
            return None
        base = f"/api/builds/{digest}"
        bust = f"?v={re.sub(r'[^0-9]', '', report.get('built_at') or '')}"
        return {
            "model": f"{base}/model.glb{bust}",
            "preview_iso": f"{base}/preview_iso.png{bust}",
            "preview_front": f"{base}/preview_front.png{bust}",
            "preview_top": f"{base}/preview_top.png{bust}",
            **{f"preview_{name}": f"{base}/preview_{name}.png{bust}" for name in PREVIEW_NAMES
               if name not in ("iso", "front", "top") and (builds.build_path(digest) / f"preview_{name}.png").is_file()},
            **({name: f"{base}/{name}.png{bust}" for name in CHARACTER_PREVIEWS}
               if report.get("kind") == "characters" else {}),
            "report": f"{base}/report.json",
            "log": f"{base}/build.log",
        }

    def node(row: VariantRow) -> dict[str, Any]:
        state = builds.state_of(row.hash)
        artifact = urls(row.hash) if state in ("ok", "failed") else None
        return {
            "id": row.vid, "parent": row.parent, "status": row.status, "level": row.level, "rating": row.rating,
            "tags": json.loads(row.tags), "note": row.note, "author": row.author, "created": row.created,
            "hash": row.hash, "build_state": state, "error": row.error,
            "preview": card_preview(artifact) if artifact else None,
        }

    def card_preview(artifact: dict[str, str]) -> str:
        """Characters are shown posed (idle), never in the rest A-pose."""
        return artifact.get("preview_pose") or artifact["preview_iso"]

    def ensure_entity(kind: Kind, entity_id: str) -> None:
        if not store.has_entity(kind, entity_id):
            raise HTTPException(404, f"{kind}/{entity_id} not found")

    def variant_detail(kind: Kind, entity_id: str, vid: str) -> dict[str, Any]:
        variant = store.variant(kind, entity_id, vid)
        out: dict[str, Any] = {"kind": kind, "entity_id": entity_id, "id": vid,
                               "variant": variant_to_yaml_dict(variant), "errors": []}
        try:
            res = planner().resolve(kind, entity_id, vid)
        except RecipeError as exc:
            out["errors"] = exc.errors
            return out
        out.update(resolution_payload(res))
        out["build_state"] = builds.state_of(res.hash)
        out["report"] = builds.read_report(res.hash)
        out["urls"] = urls(res.hash)
        return out

    def resolution_payload(res: Resolution) -> dict[str, Any]:
        data: dict[str, Any] = {"chain": res.chain, "params": res.params, "sources": res.sources,
                                "changed": res.changed, "hash": res.hash}
        if res.source is not None:
            data["source"] = {"variant": res.source.variant, "file": res.source.path.name,
                              "own": res.source.variant == res.variant.id,
                              "open": sessions.is_open(res.source.path)}
        if isinstance(res, ComponentResolution) and res.entity.kind == "materials":
            data["shader"] = res.entity.shader
            data["models"] = [{"ref": m["ref"], "hash": m["hash"], "url": f"/api/builds/{m['hash']}/model.glb"}
                              for m in res.models]
        if isinstance(res, AssetResolution):
            data["changed_slots"] = res.changed_slots
            data["changed_offsets"] = res.changed_offsets
            data["slots"] = [
                {"name": s.name, "socket": s.spec.socket, "host": s.host, "ref": s.ref, "source": s.source,
                 "offset": s.offset, "offset_source": s.offset_source,
                 "required": s.spec.required, "changed": s.name in res.changed_slots,
                 "offset_changed": s.name in res.changed_offsets,
                 "kind": s.component.entity.kind if s.component else None,
                 "component": s.component.entity.id if s.component else None,
                 "variant": s.component.variant.id if s.component else None,
                 "hash": s.component.hash if s.component else None,
                 "params": s.component.params if s.component else None}
                for s in res.slots.values()
            ]
        return data

    def flatten(res: Resolution) -> dict[str, Any]:
        if isinstance(res, ComponentResolution):
            return dict(res.params)
        flat: dict[str, Any] = {f"params.{k}": v for k, v in res.params.items()}
        for s in res.slots.values():
            flat[s.name] = s.ref
            for axis, value in zip("xyz", s.offset):
                flat[f"slot_offsets.{s.name}.{axis}"] = value
            if s.component:
                flat.update({f"{s.name}.{k}": v for k, v in s.component.params.items()})
        return flat

    def parse_ref(ref: str) -> tuple[Kind, str, str]:
        parts = ref.strip("/").split("/")
        if len(parts) != 3 or parts[0] not in KINDS:
            raise HTTPException(400, f"bad reference '{ref}', expected <kind>/<id>/<vid>")
        return parts[0], parts[1], parts[2]  # type: ignore[return-value]

    # ------------------------------------------------------------------ fixed routes
    @app.get("/api/palette")
    def get_palette() -> dict[str, Any]:
        return store.palette().as_dict()

    @app.get("/api/diff")
    def diff(a: str = Query(...), b: str = Query(...)) -> dict[str, Any]:
        p = planner()
        res_a, res_b = p.resolve(*parse_ref(a)), p.resolve(*parse_ref(b))
        flat_a, flat_b = flatten(res_a), flatten(res_b)
        keys = list(dict.fromkeys([*flat_a, *flat_b]))
        rows = [{"key": k, "a": flat_a.get(k), "b": flat_b.get(k), "changed": flat_a.get(k) != flat_b.get(k)}
                for k in keys]
        return {"a": {"ref": a, "hash": res_a.hash}, "b": {"ref": b, "hash": res_b.hash}, "rows": rows,
                "changed": sum(r["changed"] for r in rows)}

    # ------------------------------------------------------------------ legacy (read-only catalog)
    @app.get("/api/legacy")
    def legacy_list() -> dict[str, Any]:
        items = sorted(legacy.scan(), key=lambda i: (i.source, i.folder, i.name.lower()))
        return {"sources": legacy.sources(), "stats": legacy_stats(legacy),
                "items": [legacy.summary(i) for i in items]}

    @app.get("/api/legacy/items/{item_id}")
    def legacy_item(item_id: str) -> dict[str, Any]:
        item = legacy.item(item_id)
        if item is None:
            raise HTTPException(404, "legacy item not found")
        return legacy.summary(item, full=True)

    @app.post("/api/legacy/build")
    async def legacy_build(force: bool = False) -> dict[str, Any]:
        targets = legacy.scan(max_age=0) if force else legacy.stale()
        for item in targets:
            await legacy.submit(item, force=force)
        return {"queued": len(targets)}

    @app.post("/api/legacy/items/{item_id}/rebuild")
    async def legacy_rebuild(item_id: str) -> dict[str, str]:
        item = legacy.item(item_id)
        if item is None:
            raise HTTPException(404, "legacy item not found")
        return {"state": await legacy.submit(item, force=True)}

    @app.get("/api/legacy/files/{digest}/{name}")
    def legacy_file(digest: str, name: str) -> FileResponse:
        if not _HASH_RE.match(digest) or name not in LEGACY_ARTIFACTS:
            raise HTTPException(404, "unknown artifact")
        path = legacy.artifact_dir(digest) / name
        if not path.is_file():
            raise HTTPException(404, "artifact not built")
        return FileResponse(path, media_type=_MEDIA.get(path.suffix, "application/octet-stream"),
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/material-presets")
    def material_presets() -> list[dict[str, Any]]:
        """All usable material variants with resolved params (the viewer applies them live)."""
        p = planner()
        out: list[dict[str, Any]] = []
        for eid in store.entity_ids("materials"):
            try:
                doc = p.entity("materials", eid)
            except RecipeError:
                continue
            if doc.abstract:
                continue
            for vid, variant in p.variants("materials", eid).items():
                if variant.status == "archived":
                    continue
                try:
                    res = p.resolve_component(eid, vid, "materials")
                except RecipeError:
                    continue
                out.append({"ref": f"{eid}@{vid}", "id": eid, "vid": vid, "title": doc.title, "shader": doc.shader,
                            "note": variant.note, "status": variant.status, "params": res.params})
        return out

    @app.get("/api/materials/{entity_id}/godot/{name}")
    def godot_shader(entity_id: str, name: str) -> FileResponse:
        ensure_entity("materials", entity_id)
        path = store.entity_file("materials", entity_id, name)
        if path.suffix != ".gdshader" or not path.is_file():
            raise HTTPException(404, "no such shader")
        return FileResponse(path, media_type="text/plain", filename=name)

    @app.get("/api/materials/{entity_id}/variants/{vid}/godot.tres")
    def godot_material(entity_id: str, vid: str) -> PlainTextResponse:
        ensure_entity("materials", entity_id)
        p = planner()
        doc = p.entity("materials", entity_id)
        res = p.resolve_component(entity_id, vid, "materials")
        text = godot_tres(doc, res.params, f"{entity_id}@{vid}")
        return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="{entity_id}_{vid}.tres"'})

    @app.get("/api/builds/events")
    async def build_events(request: Request) -> StreamingResponse:
        queue = bus.subscribe()

        async def stream() -> AsyncIterator[str]:
            try:
                yield "retry: 3000\n\n"
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        yield ": ping\n\n"
                        continue
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            finally:
                bus.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/builds/queue")
    def build_queue() -> list[dict[str, Any]]:
        return builds.queue_snapshot()

    @app.get("/api/builds/{digest}/{name}")
    def build_artifact(digest: str, name: str) -> FileResponse:
        if not _HASH_RE.match(digest) or name not in ARTIFACTS:
            raise HTTPException(404, "unknown artifact")
        path = builds.build_path(digest) / name
        if not path.is_file():
            raise HTTPException(404, "artifact not built")
        media = _MEDIA.get(path.suffix, "application/octet-stream")
        return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})

    @app.post("/api/reindex")
    def reindex() -> dict[str, int]:
        with settings_lock:
            return index.reindex(planner(), cfg.build_dir)

    @app.get("/api/registry-settings")
    def registry_settings() -> RegistrySettings:
        return RegistrySettings(priority_tags=cfg.priority_tags)

    @app.put("/api/registry-settings")
    def update_registry_settings(body: RegistrySettings) -> RegistrySettings:
        with settings_lock:
            try:
                save_priority_tags(cfg, body.priority_tags)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                raise HTTPException(500, f"could not save project config: {exc}") from exc
            cfg.priority_tags = body.priority_tags
        return RegistrySettings(priority_tags=cfg.priority_tags)

    @app.get("/api/tags")
    def catalog_tags() -> dict[str, Any]:
        return tags.inventory()

    def publish_tag_changes(refs: list[EntityRef]) -> None:
        for kind, eid in refs:
            bus.publish({"type": "entity", "kind": kind, "id": eid, "state": "updated"})

    def change_tag(name: str, new: str | None) -> dict[str, Any]:
        try:
            return tags.change(name, new, notify=publish_tag_changes)
        except (RecipeError, FileNotFoundError):
            raise
        except Exception as exc:
            raise HTTPException(500, f"could not update tags: {exc}") from exc

    @app.patch("/api/tags/{name:path}")
    def rename_tag(name: str, body: TagRename) -> dict[str, Any]:
        return change_tag(name, body.name)

    @app.delete("/api/tags/{name:path}")
    def delete_tag(name: str) -> dict[str, Any]:
        return change_tag(name, None)

    @app.get("/api/compose/options")
    def compose_options() -> dict[str, list[dict[str, Any]]]:
        """Catalog of selectable variants for a new composition, including socket contracts."""
        p = planner()
        items: list[dict[str, Any]] = []
        for kind in ("components", "assets"):
            for eid in store.entity_ids(kind):
                try:
                    doc = p.entity(kind, eid)
                except RecipeError:
                    continue
                if doc.abstract or doc.interface is None:
                    continue
                for vid, variant in p.variants(kind, eid).items():
                    if variant.status == "archived":
                        continue
                    try:
                        res = p.resolve(kind, eid, vid)
                    except RecipeError:
                        continue
                    built = builds.state_of(res.hash) == "ok"
                    ref = f"{kind}/{eid}@{vid}"
                    items.append({
                        "ref": ref, "kind": kind, "id": eid, "title": doc.title or eid,
                        "variant": vid, "status": variant.status, "built": built,
                        "level": variant.level, "type": doc.type, "category": doc.category,
                        "grid_size": list(doc.interface.grid_size),
                        "voxel_size": doc.interface.voxel_size, "mounts": doc.interface.mounts,
                        "sockets": [socket.model_dump(mode="json") for socket in doc.interface.sockets],
                        "preview": (urls(res.hash) or {}).get("preview_iso") if built else None,
                        "hash": res.hash,
                    })
        return {"items": items}

    @app.get("/api/catalog-groups")
    def get_catalog_groups() -> dict[str, Any]:
        return {"groups": store.catalog_groups()}

    @app.get("/api/blockout-sheets/files/{digest}/{name}")
    def blockout_sheet_file(digest: str, name: str) -> FileResponse:
        path = workbench.file(digest, name)
        return FileResponse(path, media_type=_MEDIA.get(path.suffix, "application/octet-stream"), filename=name,
                            content_disposition_type="inline" if path.suffix == ".png" else "attachment")

    @app.get("/api/blockout-sheets/{group_id}")
    def get_blockout_sheet(group_id: str, asset: str | None = None, v: str | None = None) -> dict[str, Any]:
        return workbench.snapshot(group_id, asset, v)

    @app.get("/api/assets/{entity_id}/blockout-sheets")
    def asset_blockout_sheets(entity_id: str, v: str | None = None) -> dict[str, Any]:
        return workbench.discovery(entity_id, v)

    @app.post("/api/blockout-sheets/{group_id}/build")
    async def build_blockout_sheet(group_id: str, asset: str | None = None, v: str | None = None) -> dict[str, Any]:
        return await workbench.build_missing(group_id, asset, v)

    @app.post("/api/blockout-sheets/{group_id}/blender")
    async def open_blockout_sheet(group_id: str, body: OpenBlockoutSheet,
                                  asset: str | None = None, v: str | None = None) -> dict[str, Any]:
        try:
            return await workbench.blender(group_id, asset, v, open_gui=body.open)
        except BlenderLaunchError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.post("/api/blockout-sheets/{group_id}/projections")
    async def blockout_sheet_projections(group_id: str, asset: str | None = None, v: str | None = None) -> dict[str, Any]:
        try:
            return await workbench.blender(group_id, asset, v, open_gui=False)
        except BlenderLaunchError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.put("/api/catalog-groups")
    def put_catalog_groups(body: CatalogGroups) -> dict[str, Any]:
        seen_groups: set[str] = set()
        seen_items: set[str] = set()
        groups: list[dict[str, Any]] = []
        for group in body.groups:
            gid = check_id(group.id)
            if gid in seen_groups:
                raise RecipeError(f"duplicate catalog group '{gid}'")
            if not group.title.strip():
                raise RecipeError(f"catalog group '{gid}' needs a title")
            seen_groups.add(gid)
            items: list[str] = []
            for ref in group.items:
                kind, sep, eid = ref.partition("/")
                if not sep or kind not in ("components", "assets") or not store.has_entity(kind, eid):
                    raise RecipeError(f"catalog group '{gid}': unknown item '{ref}'")
                if ref in seen_items:
                    raise RecipeError(f"catalog item '{ref}' appears in more than one group")
                seen_items.add(ref)
                items.append(ref)
            groups.append({"id": gid, "title": group.title.strip(), "items": items})
        store.save_catalog_groups(groups)
        bus.publish({"type": "catalog_groups", "state": "updated"})
        return {"groups": groups}

    @app.post("/api/assets", status_code=201)
    async def create_asset(body: NewAsset) -> dict[str, Any]:
        """Persist a new asset base + v001, validate the complete graph, optionally build it."""
        entity_id = check_id(body.id)
        if not body.title.strip():
            raise RecipeError("asset title is required")
        if body.pivot not in ("bottom_center", "ground"):
            raise RecipeError("pivot must be bottom_center or ground")
        if any(isinstance(v, bool) or v <= 0 for v in body.grid_size):
            raise RecipeError("grid_size coordinates must be positive integers")
        palette_size = store.palette().voxel_size
        if not math.isfinite(body.voxel_size) or body.voxel_size != palette_size:
            raise RecipeError(f"voxel_size must equal palette voxel_size ({palette_size})")
        if not body.slots:
            raise RecipeError("asset needs at least one slot")
        for name, spec in body.slots.items():
            check_id(name)
            if any(isinstance(v, bool) or v <= 0 for v in spec.max_grid):
                raise RecipeError(f"slot '{name}': max_grid coordinates must be positive integers")
        bodies = [name for name, spec in body.slots.items() if spec.socket is None]
        if len(bodies) != 1:
            raise RecipeError("asset needs exactly one body slot (socket: null)")
        sockets = list(body.sockets)
        if len({s.name for s in sockets}) != len(sockets):
            raise RecipeError("duplicate exported socket names")
        for socket in sockets:
            if not socket.name or any(not math.isfinite(v) for v in (*socket.position, *socket.rotation)):
                raise RecipeError(f"invalid exported socket '{socket.name}'")
        from .models import EntityDoc, Interface
        p = planner()
        draft_doc = EntityDoc(kind="assets", id=entity_id, title=body.title.strip(), type="structure",
                              interface=Interface(grid_size=body.grid_size, voxel_size=body.voxel_size,
                                                  pivot=body.pivot, sockets=sockets), slots=body.slots)
        _, slot_hosts, graph_errors = p.slot_order(draft_doc)
        if graph_errors:
            raise RecipeError(graph_errors)
        if not sockets:
            body_name = bodies[0]
            body_ref = body.variant.slots.get(body_name)
            if body_ref:
                ref_kind, ref_id, ref_vid = parse_entity_slot_ref(body_ref)
                child = p.resolve(ref_kind, ref_id, ref_vid)
                interface = child.entity.interface
                if interface is not None:
                    used = {link[1] for link in slot_hosts.values()
                            if link is not None and link[0] == body_name}
                    offset = body.variant.slot_offsets.get(body_name, (0.0, 0.0, 0.0))
                    sockets = [Socket(name=f"{body_name}.{socket.name}", type=socket.type,
                                      position=tuple(a + b for a, b in zip(socket.position, offset)),
                                      rotation=socket.rotation, description=socket.description)
                               for socket in interface.sockets if socket.name not in used]
        meta = {
            "id": entity_id, "title": body.title.strip(), "type": "structure",
            "inherits": None, "generator_version": 1, "complexity_level": body.variant.level,
            "export_sockets": True, "tags": body.tags,
            "interface": {"grid_size": list(body.grid_size), "voxel_size": body.voxel_size,
                          "pivot": body.pivot,
                          "sockets": [socket.model_dump(mode="json") for socket in sockets]},
            "params": {},
            "slots": {name: spec.model_dump(mode="json") for name, spec in body.slots.items()},
        }
        variant = AssetVariant(id="v001", parent=None, slots=body.variant.slots,
                               slot_offsets=body.variant.slot_offsets, params_delta={},
                               level=body.variant.level, author=body.variant.author,
                               note=body.variant.note or f"Initial composition of {body.title.strip()}",
                               tags=body.variant.tags, status="draft", created=now_iso())
        with settings_lock:
            folder = store.create_asset(meta, body.description, variant)
            try:
                p = planner()
                p.resolve_asset(entity_id, "v001")
                p.plan("assets", entity_id, "v001")
            except Exception:
                shutil.rmtree(folder)
                raise
            index.reindex(planner(), cfg.build_dir)
        bus.publish({"type": "entity", "kind": "assets", "id": entity_id, "state": "created"})
        submit = await builds.submit("assets", entity_id, "v001") if body.build else None
        detail = variant_detail("assets", entity_id, "v001")
        detail["entity"] = planner().entity("assets", entity_id).model_dump(mode="json")
        detail["submit"] = submit.__dict__ if submit else None
        return detail

    @app.get("/api/assets/{entity_id}/slot-options")
    def slot_options(entity_id: str) -> dict[str, Any]:
        ensure_entity("assets", entity_id)
        options = planner().slot_options(entity_id)
        availability: dict[str, tuple[str, str | None]] = {}
        for items in options.values():
            for item in items:
                digest = item["hash"]
                if digest not in availability:
                    report = builds.read_report(digest)
                    job = builds.jobs.get(digest)
                    state = job.state if job else (
                        "none" if report is None else "ok" if report.get("status") == "ok" else "failed"
                    )
                    preview = None
                    if state == "ok" and (builds.build_path(digest) / "preview_iso.png").is_file():
                        preview = (urls(digest, report=report) or {}).get("preview_iso")
                    availability[digest] = state, preview
                item["build_state"], item["preview"] = availability[digest]
        return options

    # ------------------------------------------------------------------ entity routes
    def character_card(kind: Kind, entity_id: str, p: Planner,
                       report: dict[str, Any] | None) -> dict[str, Any] | None:
        """Rig and clips for character cards: declared in _base.md, confirmed by the chosen build."""
        if kind != "characters":
            return None
        try:
            spec = p.entity(kind, entity_id).character
        except RecipeError:
            return None
        stats = (report or {}).get("stats", {})
        return {"rig": (spec.rig if spec else None), "clips": spec.clips if spec else [],
                "built_clips": [a["name"] for a in stats.get("animations", [])],
                "polys": stats.get("faces")}

    @app.get("/api/character-cast")
    def character_cast() -> dict[str, Any]:
        """The character showcase: registry/characters/cast.yaml resolved to built models."""
        path = store.kind_dir("characters") / "cast.yaml"
        if not path.is_file():
            raise HTTPException(404, "registry/characters/cast.yaml not found")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        p = planner()
        members = []
        for ref in data.get("members", []):
            eid, _, vid = str(ref).partition("@")
            member: dict[str, Any] = {"ref": ref, "id": eid, "vid": vid, "title": eid, "hash": None,
                                      "build_state": "none", "model": None, "preview": None, "error": None}
            try:
                res = p.resolve("characters", eid, vid)
                member["title"] = res.entity.title or eid
                member["hash"] = res.hash
                member["build_state"] = builds.state_of(res.hash)
                artifact = urls(res.hash)
                if artifact and member["build_state"] == "ok":
                    member["model"] = artifact["model"]
                    member["preview"] = card_preview(artifact)
            except RecipeError as exc:
                member["error"] = "; ".join(exc.errors)
            members.append(member)
        return {"title": data.get("title", "Каст"), "note": data.get("note", ""),
                "spacing": float(data.get("spacing", 1.35)), "members": members}

    # ------------------------------------------------------------------ Reference Lab
    lab = ReferenceLab(cfg)

    def _lab_call(fn: Any, *args: Any) -> Any:
        try:
            return fn(*args)
        except ReferenceLabError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/references")
    def references() -> dict[str, Any]:
        """Reference Lab: external character references (study only) and the templates made from them."""
        return {"references": [lab.summary(rid) for rid in lab.ids()], "templates": lab.template_list()}

    @app.get("/api/references/{ref_id}")
    def reference_detail(ref_id: str) -> dict[str, Any]:
        return _lab_call(lab.detail, ref_id)

    @app.get("/api/references/{ref_id}/files/{rel:path}")
    def reference_file(ref_id: str, rel: str) -> FileResponse:
        path = _lab_call(lab.file, ref_id, rel)
        return FileResponse(path, media_type=_MEDIA.get(path.suffix, "application/octet-stream"),
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/character-templates/{kind}/{template_id}/{name}")
    def character_template_file(kind: str, template_id: str, name: str) -> FileResponse:
        path = _lab_call(lab.template_file, kind, template_id, name)
        return FileResponse(path, media_type=_MEDIA.get(path.suffix, "application/octet-stream"),
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/reference-lab/characters")
    def lab_characters() -> list[dict[str, Any]]:
        """Built character variants for the comparison side of the Lab (same camera, scale, light)."""
        p = planner()
        out = []
        for row in index.variants("characters"):
            if row.status == "archived" or builds.state_of(row.hash) != "ok":
                continue
            artifact = urls(row.hash) or {}
            try:
                res = p.resolve("characters", row.entity_id, row.vid)
                title, template = res.entity.title or row.entity_id, res.params.get("body_template", "procedural")
            except RecipeError:
                continue
            out.append({"ref": f"{row.entity_id}@{row.vid}", "id": row.entity_id, "vid": row.vid, "title": title,
                        "body_template": template, "status": row.status, "model": artifact.get("model"),
                        "preview": card_preview(artifact) if artifact else None})
        return out

    @app.get("/api/{kind}")
    def list_entities(kind: Kind) -> list[dict[str, Any]]:
        # Variants with identical recipes share one build. Keep reports local to this
        # request so cards reuse disk reads while external CLI rebuilds remain visible.
        reports: dict[str, dict[str, Any] | None] = {}

        def report_for(digest: str | None) -> dict[str, Any] | None:
            if not digest:
                return None
            if digest not in reports:
                reports[digest] = builds.read_report(digest)
            return reports[digest]

        def state_for(digest: str | None) -> str:
            if not digest:
                return "none"
            job = builds.jobs.get(digest)
            if job is not None:
                return job.state
            report = report_for(digest)
            if report is None:
                return "none"
            return "ok" if report.get("status") == "ok" else "failed"

        p = planner()
        variants_by_entity: dict[str, list[VariantRow]] = {}
        for row in index.variants(kind):
            variants_by_entity.setdefault(row.entity_id, []).append(row)
        out = []
        for entity in index.entities(kind):
            rows = variants_by_entity.get(entity.entity_id, [])
            ok_rows = [r for r in rows if state_for(r.hash) == "ok"]
            pick = ([r for r in ok_rows if r.status == "approved"] or ok_rows)[-1:] or [None]
            counts: dict[str, int] = {}
            for r in rows:
                counts[r.status] = counts.get(r.status, 0) + 1
            chosen = pick[0]
            report = report_for(chosen.hash) if chosen else None
            artifact = urls(chosen.hash, report=report) if chosen else None
            out.append({
                "kind": kind, "id": entity.entity_id, "title": entity.title, "type": entity.type,
                "category": entity.category,
                "inherits": entity.inherits, "abstract": entity.abstract,
                "complexity_level": entity.complexity_level, "tags": json.loads(entity.tags),
                "variant_tags": sorted({t for r in rows for t in json.loads(r.tags)}),
                "variant_count": len(rows), "status_counts": counts, "error": entity.error,
                "preview": {"vid": chosen.vid, "status": chosen.status,
                            "url": card_preview(artifact or {"preview_iso": None}),
                            "model": (artifact or {}).get("model")} if chosen else None,
                "character": character_card(kind, entity.entity_id, p, report),
            })
        return out

    @app.get("/api/{kind}/{entity_id}")
    def get_entity(kind: Kind, entity_id: str) -> dict[str, Any]:
        ensure_entity(kind, entity_id)
        doc = planner().entity(kind, entity_id)
        data = doc.model_dump(mode="json")
        data["markdown"] = f"---\n{frontmatter.dump_yaml(doc.frontmatter)}---\n\n{doc.description}\n"
        return data

    @app.get("/api/{kind}/{entity_id}/tree")
    def get_tree(kind: Kind, entity_id: str) -> dict[str, Any]:
        ensure_entity(kind, entity_id)
        rows = index.variants(kind, entity_id)
        return {"nodes": [node(r) for r in rows],
                "edges": [{"from": r.parent, "to": r.vid} for r in rows if r.parent]}

    @app.get("/api/{kind}/{entity_id}/variants/{vid}")
    def get_variant(kind: Kind, entity_id: str, vid: str) -> dict[str, Any]:
        ensure_entity(kind, entity_id)
        return variant_detail(kind, entity_id, vid)

    @app.post("/api/{kind}/{entity_id}/variants", status_code=201)
    async def create_variant(kind: Kind, entity_id: str, body: NewVariant) -> dict[str, Any]:
        ensure_entity(kind, entity_id)
        p = planner()
        entity = p.entity(kind, entity_id)
        if entity.abstract:
            raise RecipeError(f"{kind}/{entity_id} is abstract")
        parent_res = p.resolve(kind, entity_id, body.parent) if body.parent else None
        level = body.level if body.level is not None else (
            parent_res.variant.level if parent_res else entity.complexity_level)
        vid = store.next_vid(kind, entity_id)
        common = {"id": vid, "parent": body.parent, "level": level, "author": body.author, "note": body.note,
                  "tags": body.tags, "status": "draft", "created": now_iso()}
        variant: Variant
        if kind != "assets":
            delta = p.check_component_delta(entity_id, body.parent, body.delta, kind)
            if parent_res:
                delta = {k: v for k, v in delta.items() if parent_res.params.get(k) != v}
            variant = ComponentVariant(**common, delta=delta)
        else:
            params_delta = p.check_asset_delta(entity_id, body.parent, body.slots, body.params_delta)
            slots = dict(body.slots)
            slot_offsets = p.check_slot_offsets(entity_id, body.slot_offsets)
            if isinstance(parent_res, AssetResolution):
                params_delta = {k: v for k, v in params_delta.items() if parent_res.params.get(k) != v}
                slots = {k: v for k, v in slots.items() if parent_res.slots[k].ref != v}
                slot_offsets = {k: v for k, v in slot_offsets.items() if parent_res.slots[k].offset != v}
            variant = AssetVariant(**common, slots=slots, slot_offsets=slot_offsets,
                                   params_delta=params_delta)

        with settings_lock:
            path = store.save_variant(kind, entity_id, variant)
            p.forget_variants(kind, entity_id)
            try:
                p.resolve(kind, entity_id, vid)
            except RecipeError:
                path.unlink(missing_ok=True)
                raise
            index.upsert_variant(p, kind, entity_id, variant)
        bus.publish({"type": "variant", "kind": kind, "id": entity_id, "vid": vid, "state": "created"})
        submit = await builds.submit(kind, entity_id, vid) if body.build else None
        detail = variant_detail(kind, entity_id, vid)
        detail["submit"] = submit.__dict__ if submit else None
        return detail

    @app.post("/api/{kind}/{entity_id}/variants/{vid}/blender")
    async def open_in_blender(kind: Kind, entity_id: str, vid: str, body: OpenInBlender,
                              request: Request) -> dict[str, Any]:
        """Open manual geometry in the Blender GUI; by default as a new child variant of `vid`.

        A component opens as its generated parts; an asset as its whole composition, one
        object tree per slot.
        """
        if kind not in ("components", "assets"):
            raise HTTPException(400, f"{kind} cannot be edited in Blender")
        ensure_entity(kind, entity_id)
        p = planner()
        res = p.resolve(kind, entity_id, vid)
        if body.fork:
            try:
                target = await manual.fork(cfg, p, kind, entity_id, vid, note=body.note)
            except BlenderLaunchError as exc:
                raise HTTPException(502, str(exc)) from exc
            index.upsert_variant(p, kind, entity_id, store.variant(kind, entity_id, target))
            bus.publish({"type": "variant", "kind": kind, "id": entity_id, "vid": target, "state": "created"})
        else:
            # Approved geometry stays fixed; inherited files belong to the ancestor that owns them.
            if res.source is None or res.source.variant != vid:
                raise HTTPException(409, f"у {vid} нет своего .blend — создайте ветку в Blender")
            if res.variant.status in ("approved", "archived"):
                raise HTTPException(409, f"{vid} в статусе {res.variant.status} — создайте ветку в Blender")
            target = vid
        target_res = planner().resolve(kind, entity_id, target)
        interface = target_res.entity.interface
        assert target_res.source is not None and interface is not None
        session_args = [
            "--ref", f"{kind}/{entity_id}@{target}",
            "--server", str(request.base_url).rstrip("/"),
            "--palette", json.dumps(store.palette().colors),
            "--sockets", ",".join(interface.socket_names()),
            "--grid", ",".join(str(v) for v in interface.grid_size),
            "--voxel-size", str(interface.voxel_size),
            "--pivot", interface.pivot,
        ]
        try:
            session = await sessions.open(target_res.source.path, session_args)
        except BlenderLaunchError as exc:
            # A fork is already saved, so report the launch failure next to the new variant.
            session = {"state": "error", "error": str(exc)}
        detail = variant_detail(kind, entity_id, target)
        detail["blender"] = session
        return detail

    @app.post("/api/{kind}/{entity_id}/variants/{vid}/rebuild")
    async def rebuild(kind: Kind, entity_id: str, vid: str) -> dict[str, Any]:
        ensure_entity(kind, entity_id)
        store.variant(kind, entity_id, vid)
        result = await builds.submit(kind, entity_id, vid, force=True)
        return result.__dict__

    @app.patch("/api/{kind}/{entity_id}/variants/{vid}")
    def patch_variant(kind: Kind, entity_id: str, vid: str, body: VariantPatch) -> dict[str, Any]:
        ensure_entity(kind, entity_id)
        with settings_lock:
            variant = store.variant(kind, entity_id, vid)
            for name in body.model_fields_set:
                setattr(variant, name, getattr(body, name))
            store.save_variant(kind, entity_id, variant)
            index.upsert_variant(planner(), kind, entity_id, variant)
        bus.publish({"type": "variant", "kind": kind, "id": entity_id, "vid": vid, "state": "updated",
                     "status": variant.status})
        return variant_detail(kind, entity_id, vid)

    # ------------------------------------------------------------------ frontend
    guide = ROOT / "docs" / "guide"
    if (guide / "index.html").is_file():
        app.mount("/guide", StaticFiles(directory=guide, html=True), name="guide")
    if (FRONTEND_DIST / "index.html").is_file():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    else:
        @app.get("/", response_class=HTMLResponse)
        def no_frontend() -> str:
            return ("<h1>Voxel Asset Registry</h1><p>Frontend is not built. Run "
                    "<code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code>. "
                    "API docs: <a href='/docs'>/docs</a></p>")

    return app
