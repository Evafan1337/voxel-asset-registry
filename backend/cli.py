"""`python -m registry <command>` entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .builds import BuildService, EventBus, Target
from .config import SEED_DIR, Config, load_config
from .godot import godot_tres
from .index import Index
from .models import KINDS, Kind
from .planner import Planner
from .preflight import (
    STARTER_MANIFEST, checks_ok, environment_checks, find_godot, render_checks, starter_targets,
)
from .resolve import RecipeError, validate_schema_defaults
from .store import Store


def _parse_target(ref: str) -> Target:
    parts = ref.strip("/").split("/")
    if len(parts) != 3 or parts[0] not in KINDS:
        raise SystemExit(f"bad reference '{ref}': expected components/<id>/<vid> or assets/<id>/<vid>")
    kind: Kind = parts[0]  # type: ignore[assignment]
    return kind, parts[1], parts[2]


# ---------------------------------------------------------------------- commands

def cmd_init(cfg: Config, args: argparse.Namespace) -> int:
    created = skipped = 0
    for src in sorted(SEED_DIR.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        dst = cfg.registry_dir / src.relative_to(SEED_DIR)
        if dst.exists() and not args.force:
            skipped += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        created += 1
    cfg.build_dir.mkdir(parents=True, exist_ok=True)
    stats = Index(cfg.db_path).reindex(Planner(Store(cfg.registry_dir), cfg), cfg.build_dir)
    print(f"registry: {cfg.registry_dir}  (+{created} files, {skipped} kept)")
    print(f"index: {stats['entities']} entities, {stats['variants']} variants, {stats['builds']} builds")
    return 0


def cmd_reindex(cfg: Config, _args: argparse.Namespace) -> int:
    stats = Index(cfg.db_path).reindex(Planner(Store(cfg.registry_dir), cfg), cfg.build_dir)
    print(f"index: {stats['entities']} entities, {stats['variants']} variants, {stats['builds']} builds")
    return 0


def cmd_check(cfg: Config, _args: argparse.Namespace) -> int:
    store = Store(cfg.registry_dir)
    planner = Planner(store, cfg)
    problems: list[str] = []
    checked = 0
    try:
        store.palette()
    except RecipeError as exc:
        problems.extend(exc.errors)
    for kind in KINDS:
        for eid in store.entity_ids(kind):
            try:
                doc = planner.entity(kind, eid)
            except RecipeError as exc:
                problems.extend(f"{kind}/{eid}: {e}" for e in exc.errors)
                continue
            problems.extend(f"{kind}/{eid}: {e}" for e in validate_schema_defaults(doc.params))
            if kind == "components" and not doc.abstract and not store.generator_path(eid).is_file():
                problems.append(f"{kind}/{eid}: generator.py missing")
            variants, file_errors = store.variants(kind, eid)
            problems.extend(file_errors)
            if doc.abstract:
                continue
            for vid in variants:
                checked += 1
                try:
                    planner.plan(kind, eid, vid)
                except RecipeError as exc:
                    problems.extend(f"{kind}/{eid}/{vid}: {e}" for e in exc.errors)
    for line in problems:
        print(f"  ✗ {line}")
    print(f"checked {checked} variants: {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


def cmd_doctor(cfg: Config, args: argparse.Namespace) -> int:
    checks = environment_checks(cfg, frontend=not args.no_frontend,
                                require_blender=args.require_blender, skip_blender=args.skip_blender)
    render_checks(checks, as_json=args.json)
    return 0 if checks_ok(checks) else 1


def cmd_build_demo(cfg: Config, args: argparse.Namespace) -> int:
    try:
        refs = starter_targets(Path(args.manifest), args.pack)
    except ValueError as exc:
        raise RecipeError(str(exc)) from exc
    planner = Planner(Store(cfg.registry_dir), cfg)
    targets = [_parse_target(ref) for ref in refs]
    # Fail before starting Blender if any selected recipe or dependency is missing.
    problems: list[str] = []
    for ref, target in zip(refs, targets):
        try:
            planner.plan(*target)
        except RecipeError as exc:
            problems.extend(f"{ref}: {error}" for error in exc.errors)
    if problems:
        raise RecipeError(problems)
    if args.list:
        print("\n".join(refs))
        print(f"{len(targets)} demo variant(s); recipes valid, no builds started")
        return 0
    checks = environment_checks(cfg, frontend=False, require_blender=True)
    render_checks(checks)
    if not checks_ok(checks):
        return 1
    return _run_builds(cfg, targets, force=args.force)


def _run_builds(cfg: Config, targets: list[Target], force: bool) -> int:
    """Build targets; materials go in a second stage (their previews use freshly built models)."""
    store = Store(cfg.registry_dir)
    index = Index(cfg.db_path)
    index.reindex(Planner(store, cfg), cfg.build_dir)
    bus = EventBus()
    results: dict[Target, dict[str, Any]] = {}

    def on_event(event: dict[str, Any]) -> None:
        if event.get("type") not in ("build", "variant") or "vid" not in event:
            return
        target = (event["kind"], event["id"], event["vid"])
        state = event.get("state")
        label = "/".join(target)
        if state == "running":
            print(f"  … {label}  building {event['hash']}", flush=True)
        elif state in ("ok", "failed", "invalid"):
            results[target] = event
            mark = "✓" if state == "ok" else "✗"
            extra = " (cached)" if event.get("cached") else ""
            err = f"  — {event['error']}" if event.get("error") else ""
            where = f"  → {cfg.build_dir / event['hash']}" if event.get("hash") else ""
            print(f"  {mark} {label}  {state}{extra}{err}{where}", flush=True)

    bus.listen(on_event)

    async def main() -> None:
        service = BuildService(cfg, store, index, bus)
        service.start()
        try:
            stages = [[t for t in targets if t[0] != "materials"], [t for t in targets if t[0] == "materials"]]
            for stage in stages:
                for kind, eid, vid in stage:
                    await service.submit(kind, eid, vid, force=force)
                await service.drain()
        finally:
            await service.stop()

    print(f"building {len(targets)} variant(s) with {cfg.blender_bin} ...")
    try:
        asyncio.run(main())
    finally:
        index.engine.dispose()
    missing = [target for target in targets if target not in results]
    for target in missing:
        print(f"  ✗ {'/'.join(target)}: build finished without a result")
    failed = [t for t, e in results.items() if e.get("state") != "ok"] + missing
    print(f"done: {len(targets) - len(failed)} ok, {len(failed)} failed")
    return 1 if failed else 0


def cmd_build(cfg: Config, args: argparse.Namespace) -> int:
    return _run_builds(cfg, [_parse_target(args.ref)], force=args.force)


def _artifact_ready(cfg: Config, digest: str, kind: Kind) -> bool:
    folder = cfg.build_dir / digest
    try:
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    artifact = "preview_iso.png" if kind == "materials" else "model.glb"
    return isinstance(report, dict) and report.get("status") == "ok" and (folder / artifact).is_file()


def cmd_build_all(cfg: Config, args: argparse.Namespace) -> int:
    store = Store(cfg.registry_dir)
    planner = Planner(store, cfg)
    targets: list[Target] = []
    invalid_entities = 0
    # components first: nicer progress output (assets are independent builds anyway)
    for kind in KINDS:
        for eid in store.entity_ids(kind):
            try:
                if planner.entity(kind, eid).abstract:
                    continue
            except RecipeError as exc:
                print(f"  ✗ {kind}/{eid}: {exc}")
                invalid_entities += 1
                continue
            for vid, variant in planner.variants(kind, eid).items():
                if variant.status == "archived":
                    continue
                if args.only_stale:
                    try:
                        digest = planner.resolve(kind, eid, vid).hash
                    except RecipeError:
                        digest = None
                    if digest and _artifact_ready(cfg, digest, kind):
                        continue
                targets.append((kind, eid, vid))
    if not targets:
        print("nothing to build")
        return 1 if invalid_entities else 0
    # The selected targets are precisely absent or unhealthy artifacts. Failed reports
    # must not be reused as cache results when the user asks to repair stale builds.
    result = _run_builds(cfg, targets, force=args.force or args.only_stale)
    return 1 if invalid_entities else result


def cmd_legacy(cfg: Config, args: argparse.Namespace) -> int:
    """List the legacy catalog; with --build render previews/GLB for new or changed files."""
    from .legacy import LegacyService

    service = LegacyService(cfg)
    items = service.scan(max_age=0)
    for src in service.sources():
        count = sum(1 for i in items if i.source == src["name"])
        print(f"{src['label']:<24} {count:>4}  {src['path']}{'' if src['exists'] else '  (нет папки)'}")
    targets = items if args.force else service.stale()
    print(f"всего {len(items)}, без превью {len(service.stale())}")
    if not args.build or not targets:
        return 0

    done = {"ok": 0, "failed": 0}
    names = {i.id: f"{i.source}/{i.folder + '/' if i.folder else ''}{i.name}" for i in items}

    def on_event(event: dict[str, Any]) -> None:
        if event.get("type") == "legacy" and event.get("state") in ("ok", "failed"):
            done[event["state"]] += 1
            mark = "✓" if event["state"] == "ok" else "✗"
            err = f"  — {event['error']}" if event.get("error") else ""
            print(f"  {mark} [{done['ok'] + done['failed']}/{len(targets)}] {names.get(event['item'], event['item'])}{err}",
                  flush=True)

    service.bus.listen(on_event)

    async def main() -> None:
        service.start()
        for item in targets:
            await service.submit(item, force=args.force)
        await service.drain()
        await service.stop()

    print(f"рендер {len(targets)} моделей, {cfg.legacy.parallel} параллельно ...")
    asyncio.run(main())
    print(f"готово: {done['ok']} ok, {done['failed']} с ошибкой")
    return 0


def _find_godot(cfg: Config) -> str | None:
    return find_godot(cfg)


def cmd_godot_preview(cfg: Config, args: argparse.Namespace) -> int:
    """Render preview models with a material variant in real Godot 4 (xvfb + software Vulkan)."""
    kind, eid, vid = _parse_target(args.ref)
    if kind != "materials":
        raise SystemExit("godot-preview expects materials/<id>/<vid>")
    godot = _find_godot(cfg)
    if not godot or not shutil.which("xvfb-run"):
        raise SystemExit("need Godot 4 (config godot_bin) and xvfb-run")
    store = Store(cfg.registry_dir)
    planner = Planner(store, cfg)
    doc = planner.entity("materials", eid)
    res = planner.resolve_component(eid, vid, "materials")
    models = [m["glb"] for m in res.models]
    if args.models:
        models = []
        for ref in args.models.split(","):
            k, e, v = _parse_target(ref)
            models.append(str(cfg.build_dir / planner.resolve(k, e, v).hash / "model.glb"))
    if not models:
        raise SystemExit("no built preview models — build assets first")

    project = cfg.build_dir / "godot_preview"
    (project / "shaders").mkdir(parents=True, exist_ok=True)
    (project / "materials").mkdir(exist_ok=True)
    tool = Path(__file__).resolve().parent.parent / "tools" / "godot_preview"
    for name in ("project.godot", "render.gd"):
        shutil.copy2(tool / name, project / name)
    for shader in store.entity_dir("materials", eid).glob("*.gdshader"):
        shutil.copy2(shader, project / "shaders" / shader.name)
    tres = project / "materials" / f"{eid}_{vid}.tres"
    tres.write_text(godot_tres(doc, res.params, f"{eid}@{vid}"), encoding="utf-8")
    out = Path(args.out) if args.out else cfg.build_dir / "godot_preview" / f"{eid}_{vid}.png"
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x800x24", godot, "--path", str(project), "--script", "render.gd",
           "--", str(out.resolve()), ",".join(models), f"res://materials/{tres.name}",
           str(res.params.get("outline_mode", "none")), str(res.params.get("outline_px", 1.5)),
           str(res.params.get("outline_color", "#000000"))]
    env = dict(os.environ)
    if Path(cfg.godot_vulkan_icd).is_file():
        env["VK_ICD_FILENAMES"] = cfg.godot_vulkan_icd
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    errors = [line for line in (proc.stdout + proc.stderr).splitlines() if "SHADER ERROR" in line or "SCRIPT ERROR" in line]
    for line in errors:
        print("  ✗", line)
    if proc.returncode != 0 or not out.is_file():
        print((proc.stdout + proc.stderr)[-2000:])
        return 1
    print(f"godot render → {out}")
    return 1 if errors else 0


def cmd_godot_check(cfg: Config, args: argparse.Namespace) -> int:
    """Import a built GLB in Godot 4 headless and check it the way a game would load it:
    Skeleton3D with the humanoid bones, skinned meshes, every clip, feet on the ground, scale."""
    kind, eid, vid = _parse_target(args.ref)
    godot = _find_godot(cfg)
    if not godot:
        raise SystemExit("need Godot 4 (config godot_bin)")
    planner = Planner(Store(cfg.registry_dir), cfg)
    res = planner.resolve(kind, eid, vid)
    glb = cfg.build_dir / res.hash / "model.glb"
    if not glb.is_file():
        raise SystemExit(f"{args.ref} is not built yet ({glb})")
    tool = Path(__file__).resolve().parent.parent / "tools" / "godot_check" / "check.gd"
    proc = subprocess.run([godot, "--headless", "--path", str(tool.parent), "--script", str(tool), "--", str(glb)],
                          capture_output=True, text=True, timeout=180)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("{")), None)
    if line is None:
        print((proc.stdout + proc.stderr)[-2000:])
        return 1
    found = json.loads(line)
    checks: list[tuple[str, bool, str]] = [("import", bool(found.get("ok")), found.get("error", "GLTFDocument loaded"))]
    if found.get("ok"):
        clips = sorted(found["clips"])
        meshes = found["meshes"]
        low, size = found["aabb_min"][1], found["aabb_size"][1]
        if kind == "characters":
            from builder import humanoid

            bones = {b.replace("_", ".") for b in found["bones"]} | set(found["bones"])
            missing = [b for b in humanoid.REQUIRED_BONES if b not in bones]
            want = (res.entity.character.clips if res.entity.character else list(humanoid.CLIPS))
            height = float(res.params["height"])
            checks += [
                ("skeleton", not missing, f"Skeleton3D with {len(found['bones'])} bones" if not missing
                 else "missing bones: " + ", ".join(missing)),
                ("skin", bool(meshes) and all(m["skinned"] for m in meshes),
                 f"{sum(m['skinned'] for m in meshes)}/{len(meshes)} meshes skinned"),
                ("clips", all(c in clips for c in want), "AnimationPlayer: " + ", ".join(clips)),
                ("grounded", abs(low) <= 0.03, f"lowest point y = {low:.3f} m"),
                ("scale", 0.9 * height <= size <= 1.2 * height, f"height {size:.2f} m for height {height} m"),
            ]
        else:
            report_path = glb.parent / "report.json"
            report = json.loads(report_path.read_text()) if report_path.is_file() else {}
            want = report.get("stats", {}).get("animations", [])
            missing = [c["name"] for c in want if c["name"] not in clips]
            checks.append(("clips", not missing, "missing: " + ", ".join(missing) if missing
                           else "AnimationPlayer: " + (", ".join(clips) or "none")))
            for expected in want:
                actual = found["clips"].get(expected["name"])
                if actual and "seconds" in expected:
                    checks.append(("duration", abs(actual["length"] - expected["seconds"]) <= .02,
                                   f"{expected['name']}: {actual['length']:.2f}s"))
    for name, ok, message in checks:
        print(f"  {'✓' if ok else '✗'} {name:<9} {message}")
    ok = all(c[1] for c in checks)
    (glb.parent / "godot_check.json").write_text(json.dumps(
        {"ok": ok, "godot": Path(godot).name, "checks": [{"name": n, "ok": o, "message": m} for n, o, m in checks],
         "found": found}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{'ok' if ok else 'FAILED'} → {glb.parent / 'godot_check.json'}")
    return 0 if ok else 1


def cmd_export_godot(cfg: Config, args: argparse.Namespace) -> int:
    """Copy built variants into a Godot project: <prefix>/<kind>/<id>/<vid>/model.glb + meta.json.
    Materials become <prefix>/materials/<id>/<vid>.tres, their shaders go to res://shaders/.
    `<kind>/<id>/*` exports every variant of the entity. Nothing is built here — build first."""
    project = Path(args.project).expanduser().resolve()
    if not (project / "project.godot").is_file():
        raise SystemExit(f"{project} is not a Godot project (no project.godot)")
    store = Store(cfg.registry_dir)
    planner = Planner(store, cfg)
    library = project / args.prefix
    targets: list[tuple[Kind, str, str]] = []
    for ref in args.refs:
        kind, eid, vid = _parse_target(ref)
        if vid == "*":
            found, _errors = store.variants(kind, eid)
            targets += [(kind, eid, v) for v in sorted(found)]
        else:
            targets.append((kind, eid, vid))
    copied = skipped = failed = 0
    for kind, eid, vid in targets:
        ref = f"{kind}/{eid}/{vid}"
        try:
            res = planner.resolve(kind, eid, vid)
        except RecipeError as exc:
            print(f"  ✗ {ref}: {'; '.join(exc.errors)}")
            failed += 1
            continue
        if kind == "materials":
            (project / "shaders").mkdir(exist_ok=True)
            for shader in store.entity_dir(kind, eid).glob("*.gdshader"):
                shutil.copy2(shader, project / "shaders" / shader.name)
            tres = library / kind / eid / f"{vid}.tres"
            tres.parent.mkdir(parents=True, exist_ok=True)
            tres.write_text(godot_tres(res.entity, res.params, f"{eid}@{vid}"), encoding="utf-8")
            print(f"  ✓ {ref} → {tres.relative_to(project)}")
            copied += 1
            continue
        out = cfg.build_dir / res.hash
        if not (out / "model.glb").is_file():
            print(f"  ✗ {ref}: not built (python -m registry build {ref})")
            failed += 1
            continue
        report = json.loads((out / "report.json").read_text(encoding="utf-8")) if (out / "report.json").is_file() else {}
        stats = report.get("stats", {})
        meta = {"ref": ref, "source": "voxel_asset_registry", "kind": kind, "id": eid, "variant": vid,
                "hash": res.hash, "title": res.entity.title, "note": res.variant.note, "level": res.variant.level,
                "tags": sorted(set(res.entity.tags) | set(res.variant.tags or [])), "status": report.get("status"),
                "bbox_m": stats.get("bbox_m"), "sockets": stats.get("sockets", []),
                "animations": stats.get("animations", []), "rig": stats.get("rig")}
        folder = library / kind / eid / vid
        meta_path = folder / "meta.json"
        if meta_path.is_file() and json.loads(meta_path.read_text(encoding="utf-8")).get("hash") == res.hash:
            skipped += 1
            continue
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / "model.glb", folder / "model.glb")
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        mark = "✓" if report.get("status") == "ok" else "!"
        print(f"  {mark} {ref} → {folder.relative_to(project)}  ({report.get('status', 'no report')})")
        copied += 1
    print(f"exported {copied}, up to date {skipped}, failed {failed} → {library}")
    return 1 if failed else 0


def cmd_reference(cfg: Config, args: argparse.Namespace) -> int:
    """Reference Lab: import / build / list external character references (references/characters/)."""
    from .references import ReferenceLabError, ReferenceLab

    lab = ReferenceLab(cfg)
    try:
        if args.action == "list":
            for rid in lab.ids():
                s = lab.summary(rid)
                t = s["totals"]
                u = s["usage"]
                perm = "production" if u.get("production_template_allowed") else (
                    "derivative" if u.get("derivative_allowed") else "study only")
                print(f"{rid:<28} {s['status']:<10} {t.get('vertices', '?'):>5} v {t.get('triangles', '?'):>5} tris"
                      f"  [{perm}]  {s['title']}  templates: {', '.join(s['templates']) or '—'}")
            return 0
        if args.action == "import":
            if not args.file:
                raise SystemExit("reference import <file.blend> --id <reference_id>")
            ref_id = args.id or Path(args.file).stem
            d = lab.import_file(Path(args.file), ref_id, args.title or "")
            print(f"imported → {d} (permissions: study only — edit reference.yaml `usage` after checking the licence)")
            args.ref_id = ref_id
        report = lab.build(args.ref_id if args.action == "import" else args.id or args.file)
    except ReferenceLabError as exc:
        print("error:", exc, file=sys.stderr)
        return 1
    if report.get("status") != "ok":
        print("failed:", report.get("error"))
        return 1
    a = report["analysis"]["totals"]
    n = report["normalization"]
    print(f"analysis: {a['objects']} objects, {a['meshes']} meshes, {a['vertices']} verts, {a['triangles']} tris, "
          f"{a['armatures']} armatures / {a['bones']} bones, {a['animations']} clips, {a['materials']} materials")
    print(f"normalized: ×{n['scale']} turn {n['turn_deg']}° → height {n['height']} m, feet on z = 0, front −Y")
    if "semantic" in report:
        print(f"semantic: {len(report['semantic']['counts'])} regions, {len(report['semantic']['landmarks'])} landmarks,"
              f" ≤{report['semantic']['max_influences']} bones per vertex")
    print(f"previews: {', '.join(sorted(report['previews']))}")
    return 0


def cmd_template(cfg: Config, args: argparse.Namespace) -> int:
    """Character templates (builder/character_templates/): list, or extract one from a reference."""
    from .references import ReferenceLabError, ReferenceLab

    lab = ReferenceLab(cfg)
    if args.action == "list":
        for t in lab.template_list():
            st = t["stats"]
            print(f"{t['kind']}/{t['id']:<20} {st.get('vertices', '?'):>5} v {st.get('triangles', '?'):>5} tris"
                  f"  pose {t['pose']}  from {t['source'].get('reference', '?')}")
        return 0
    if not args.reference or not args.id:
        raise SystemExit("template extract <reference_id> --id <template_id> [--kind body]")
    try:
        report = lab.extract_template(args.reference, args.id, args.kind, args.title or "")
    except ReferenceLabError as exc:
        print("error:", exc, file=sys.stderr)
        return 1
    if report.get("status") != "ok":
        print("failed:", report.get("error"))
        return 1
    t = report["template"]
    print(f"template {args.kind}/{args.id}: {t['stats']['vertices']} verts, {t['stats']['triangles']} tris, "
          f"≤{t['stats']['max_influences']} bones per vertex → {t['dir']}")
    print(f"repair: {t['repair']}")
    loops = ", ".join(f"{x['loop']}.{x['side']}" for x in t["support_loops"]) or "—"
    print(f"support loops: {loops}")
    return 0


def cmd_serve(cfg: Config, args: argparse.Namespace) -> int:
    import uvicorn

    from .api import create_app

    host = args.host or cfg.server.host
    port = args.port or cfg.server.port
    print(f"serving on http://{host}:{port}")
    # SSE streams from open browser tabs would otherwise keep a stopping server alive forever
    common: dict[str, Any] = {"host": host, "port": port, "log_level": "info", "timeout_graceful_shutdown": 3}
    if args.reload:
        # restart the worker when backend/ or builder/ code changes (schemas, checks, API);
        # registry data (recipes) never needs a restart — it is read from disk per request.
        # Polling instead of inotify: editors/IDEs often exhaust inotify instances and the
        # watcher then fails silently; two small directories are cheap to poll.
        os.environ.setdefault("WATCHFILES_FORCE_POLLING", "true")
        root = Path(__file__).resolve().parent.parent
        uvicorn.run("backend.api:create_app", factory=True, reload=True,
                    reload_dirs=[str(root / "backend"), str(root / "builder")], **common)
    else:
        uvicorn.run(create_app(cfg), **common)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m registry", description="Voxel Asset Registry")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create registry/ with seed data and the index")
    p.add_argument("--force", action="store_true", help="overwrite existing seed files")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("build", help="build one variant: <kind>/<id>/<vid>")
    p.add_argument("ref")
    p.add_argument("--force", action="store_true", help="ignore cached artifact")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("build-all", help="build every non-archived variant (cache is reused)")
    p.add_argument("--only-stale", action="store_true", help="only variants without an artifact for their hash")
    p.add_argument("--force", action="store_true", help="rebuild even if cached")
    p.set_defaults(func=cmd_build_all)

    sub.add_parser("reindex", help="rebuild SQLite index from files").set_defaults(func=cmd_reindex)
    sub.add_parser("check", help="validate all recipes without building").set_defaults(func=cmd_check)

    p = sub.add_parser("doctor", help="check local tools and writable data paths without changing files")
    p.add_argument("--no-frontend", action="store_true", help="do not require Node/npm for CLI-only use")
    blender_checks = p.add_mutually_exclusive_group()
    blender_checks.add_argument("--require-blender", action="store_true", help="fail without Blender 5.1+")
    blender_checks.add_argument("--skip-blender", action="store_true", help="do not probe Blender (lightweight CI)")
    p.add_argument("--json", action="store_true", help="emit a structured check report")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("build-demo", help="build the explicit public starter examples, never the full registry")
    p.add_argument("--manifest", default=str(STARTER_MANIFEST), help="starter manifest YAML")
    p.add_argument("--pack", action="append", help="build every curated reference of this pack; repeat to combine packs")
    p.add_argument("--list", "--dry-run", action="store_true", help="validate and list selected refs without Blender")
    p.add_argument("--force", action="store_true", help="rebuild cached artifacts")
    p.set_defaults(func=cmd_build_demo)

    p = sub.add_parser("legacy", help="legacy catalog of pre-registry models (--build renders previews)")
    p.add_argument("--build", action="store_true", help="render new/changed files")
    p.add_argument("--force", action="store_true", help="re-render everything")
    p.set_defaults(func=cmd_legacy)

    p = sub.add_parser("godot-preview", help="render a material variant in Godot 4 (xvfb): materials/<id>/<vid>")
    p.add_argument("ref")
    p.add_argument("--models", help="comma-separated assets/<id>/<vid>,components/<id>/<vid> (default: material preview models)")
    p.add_argument("--out", help="output PNG (default build/godot_preview/<id>_<vid>.png)")
    p.set_defaults(func=cmd_godot_preview)

    p = sub.add_parser("godot-check", help="import a built GLB in Godot 4 headless and check rig, skin, clips, scale")
    p.add_argument("ref")
    p.set_defaults(func=cmd_godot_check)

    p = sub.add_parser("export-godot", help="copy built GLBs (+ meta.json) and material .tres into a Godot project")
    p.add_argument("project", help="Godot project folder (with project.godot)")
    p.add_argument("refs", nargs="+", help="<kind>/<id>/<vid>, or <kind>/<id>/* for every variant")
    p.add_argument("--prefix", default="library/registry", help="folder inside the project (default library/registry)")
    p.set_defaults(func=cmd_export_godot)

    p = sub.add_parser("reference", help="Reference Lab: import/build/list character references (references/characters)")
    p.add_argument("action", choices=["import", "build", "list"])
    p.add_argument("file", nargs="?", help="import: the .blend to copy in; build: the reference id")
    p.add_argument("--id", help="reference id (import: default = file name)")
    p.add_argument("--title")
    p.set_defaults(func=cmd_reference)

    p = sub.add_parser("template", help="character templates: list, or extract one from a reference")
    p.add_argument("action", choices=["extract", "list"])
    p.add_argument("reference", nargs="?", help="extract: the reference id")
    p.add_argument("--id", help="template id, e.g. humanoid_01")
    p.add_argument("--kind", default="body", help="body | head | hair | clothing | hands | shoes")
    p.add_argument("--title")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("serve", help="run API + frontend")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--reload", action="store_true", help="auto-restart when backend/builder code changes")
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    cfg = load_config()
    try:
        return int(args.func(cfg, args))
    except RecipeError as exc:
        print("error:", *exc.errors, sep="\n  ", file=sys.stderr)
        return 1
