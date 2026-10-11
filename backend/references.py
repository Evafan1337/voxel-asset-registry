"""Reference Lab: external character meshes for study, and the templates extracted from them.

references/characters/<id>/            never exported to a game; not a registry entity
    source.blend                       a copy of the imported file — never modified
    reference.yaml                     provenance and permissions (a human edits `usage`)
    semantic.yaml                      joint planes + face fractions (human-authored; a suggestion is written)
    analysis.json                      what the file contains (objects, topology, rig, clips, size) + normalization
    semantic.json                      regions and landmarks computed from semantic.yaml
    normalized/normalized.blend|.glb   the mesh at 1.75 m, feet on z = 0, facing −Y (+ regions.glb)
    previews/                          front · 34 · side · back, wire_*, regions_*
    studies/body|head|clothing|hair/   R&D meshes and previews

builder/character_templates/<kind>/<id>/  production templates (template.blend/json/glb, preview.png).
A template is extracted only when the reference allows derivative and production use.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from .config import ROOT, Config

REFERENCES_DIR = ROOT / "references" / "characters"
TEMPLATES_DIR = ROOT / "builder" / "character_templates"
LAB_SCRIPT = ROOT / "builder" / "reference_lab.py"
TEMPLATE_KINDS = ("body", "head", "hair", "clothing", "hands", "shoes")
STUDY_KINDS = ("body", "head", "clothing", "hair")
TARGET_HEIGHT = 1.75


class ReferenceLabError(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_yaml(path: Path) -> dict[str, Any]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def default_metadata(ref_id: str, title: str, source_name: str, sha: str) -> str:
    """reference.yaml for a new import: unknown licence → no derivative or production use."""
    return f"""# Reference Lab: provenance and permissions of this reference.
# Permissions are changed by a human only. An unknown licence is never permission to reuse.
id: {ref_id}
title: {json.dumps(title, ensure_ascii=False)}
source_file: source.blend

author: ""
source_url: ""
license: ""
notes: ""

usage:
  visual_reference: true
  topology_study: true
  derivative_allowed: false
  production_template_allowed: false

tags:
  - humanoid
  - low_poly
  - stylized
  - body_reference

imported:
  from: {json.dumps(source_name, ensure_ascii=False)}
  sha256: {sha}
  at: "{time.strftime('%Y-%m-%dT%H:%M:%S')}"
"""


def suggest_semantic(analysis: dict[str, Any]) -> str:
    """A starting semantic.yaml from average human fractions of the normalized height — a human
    checks it against previews/wire_* and fixes the planes to the real edge loops."""
    norm = analysis.get("normalization") or {}
    H = float(norm.get("height", TARGET_HEIGHT))
    bb = norm.get("bbox") or {"max": [0.8, 0, H]}
    tip = float(bb["max"][0])
    shoulder = 0.085 * H
    wrist = tip - 0.095 * H
    elbow = shoulder + 0.45 * (wrist - shoulder)
    f = {"head_base": 0.86, "neck_base": 0.81, "chest": 0.72, "waist": 0.63, "hip": 0.49, "knee": 0.29,
         "ankle": 0.06}
    planes = {k: round(v * H, 3) for k, v in f.items()}
    planes.update({"shoulder": round(shoulder, 3), "elbow": round(elbow, 3), "wrist": round(wrist, 3)})
    lines = "\n".join(f"  {k}: {v}" for k, v in planes.items())
    return f"""# SUGGESTED from average proportions — check every plane against previews/wire_*.png and the
# vertex coordinates, then save as semantic.yaml. Coordinates: normalized mesh, metres, feet on z = 0.
pose: T
planes:
{lines}
armpit: {round(planes['neck_base'] - 0.045 * H, 3)}
neck_radius: {round(0.5 * shoulder, 3)}
"""


class ReferenceLab:
    def __init__(self, cfg: Config, root: Path = REFERENCES_DIR, templates: Path = TEMPLATES_DIR):
        self.cfg = cfg
        self.root = root
        self.templates = templates

    # ------------------------------------------------------------------ reading
    def ref_dir(self, ref_id: str) -> Path:
        path = self.root / ref_id
        if not (path / "reference.yaml").is_file():
            raise ReferenceLabError(f"reference {ref_id!r} not found in {self.root}")
        return path

    def ids(self) -> list[str]:
        return sorted(p.parent.name for p in self.root.glob("*/reference.yaml")) if self.root.is_dir() else []

    def metadata(self, ref_id: str) -> dict[str, Any]:
        return _read_yaml(self.ref_dir(ref_id) / "reference.yaml")

    def summary(self, ref_id: str) -> dict[str, Any]:
        d = self.ref_dir(ref_id)
        meta = self.metadata(ref_id)
        analysis = _read_json(d / "analysis.json") or {}
        totals = (analysis.get("analysis") or {}).get("totals", {})
        return {"id": ref_id, "title": meta.get("title", ref_id), "usage": meta.get("usage", {}),
                "license": meta.get("license", ""), "tags": meta.get("tags", []),
                "status": analysis.get("status", "not_built"), "totals": totals,
                "preview": "previews/34.png" if (d / "previews" / "34.png").is_file() else None,
                "templates": self.templates_from(ref_id)}

    def detail(self, ref_id: str) -> dict[str, Any]:
        d = self.ref_dir(ref_id)
        semantic = _read_json(d / "semantic.json") or {}
        previews = sorted(p.name for p in (d / "previews").glob("*.png")) if (d / "previews").is_dir() else []
        studies = {k: sorted(str(p.relative_to(d)) for p in (d / "studies" / k).glob("*") if p.is_file())
                   for k in STUDY_KINDS if (d / "studies" / k).is_dir()}
        models = {name: f"normalized/{name}.glb" for name in ("normalized", "regions")
                  if (d / "normalized" / f"{name}.glb").is_file()}
        return {
            **self.summary(ref_id), "metadata": self.metadata(ref_id), "analysis": _read_json(d / "analysis.json"),
            "semantic_yaml": (d / "semantic.yaml").read_text(encoding="utf-8") if (d / "semantic.yaml").is_file()
            else None,
            "semantic": {k: semantic.get(k) for k in ("counts", "landmarks", "max_influences")} if semantic else None,
            "previews": previews, "models": models, "studies": studies,
        }

    def file(self, ref_id: str, rel: str) -> Path:
        d = self.ref_dir(ref_id).resolve()
        path = (d / rel).resolve()
        if d not in path.parents or not path.is_file():
            raise ReferenceLabError(f"no file {rel!r} in reference {ref_id}")
        return path

    # ------------------------------------------------------------------ templates
    def template_list(self) -> list[dict[str, Any]]:
        out = []
        for kind in TEMPLATE_KINDS:
            for path in sorted((self.templates / kind).glob("*/template.json")):
                data = _read_json(path) or {}
                out.append({"kind": kind, "id": path.parent.name, "title": data.get("title", ""),
                            "stats": data.get("stats", {}), "pose": data.get("pose"),
                            "source": {k: v for k, v in (data.get("source") or {}).items() if k != "semantic"},
                            "extraction": data.get("extraction", {}),
                            "preview": "preview.png" if (path.parent / "preview.png").is_file() else None,
                            "model": "template.glb" if (path.parent / "template.glb").is_file() else None})
        return out

    def templates_from(self, ref_id: str) -> list[str]:
        return [f"{t['kind']}/{t['id']}" for t in self.template_list() if t["source"].get("reference") == ref_id]

    def template_file(self, kind: str, template_id: str, name: str) -> Path:
        base = (self.templates / kind / template_id).resolve()
        path = (base / name).resolve()
        if kind not in TEMPLATE_KINDS or base not in path.parents or not path.is_file():
            raise ReferenceLabError(f"no file {name!r} in template {kind}/{template_id}")
        return path

    # ------------------------------------------------------------------ actions (Blender)
    def import_file(self, source: Path, ref_id: str, title: str = "") -> Path:
        source = source.expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".blend":
            raise ReferenceLabError(f"{source} is not a .blend file")
        d = self.root / ref_id
        if (d / "reference.yaml").is_file():
            raise ReferenceLabError(f"reference {ref_id!r} already exists — use `reference build {ref_id}`")
        for sub in ("previews", "normalized", *(f"studies/{k}" for k in STUDY_KINDS)):
            (d / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, d / "source.blend")                 # the original is never touched
        sha = _sha256(d / "source.blend")
        (d / "reference.yaml").write_text(default_metadata(ref_id, title or ref_id, source.name, sha),
                                          encoding="utf-8")
        return d

    def _blender(self, blend: Path, mode: str, job: dict[str, Any], log_path: Path) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(job, f, ensure_ascii=False)
            job_path = Path(f.name)
        cmd = [self.cfg.blender_bin, "-b", "--factory-startup", str(blend), "--python-exit-code", "1",
               "-P", str(LAB_SCRIPT), "--", mode, "--job", str(job_path)]
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=self.cfg.build_timeout)
        finally:
            job_path.unlink(missing_ok=True)
        log_path.write_text(proc.stdout + proc.stderr, encoding="utf-8")
        report = _read_json(Path(job["report"])) or {"status": "failed", "error": f"exit {proc.returncode}"}
        if proc.returncode != 0 and report.get("status") == "ok":
            report = {**report, "status": "failed", "error": f"exit {proc.returncode}"}
        return report

    def build(self, ref_id: str) -> dict[str, Any]:
        """Analysis, normalization, previews, GLB — and regions when semantic.yaml exists."""
        d = self.ref_dir(ref_id)
        semantic = _read_yaml(d / "semantic.yaml") or None
        job = {"ref_dir": str(d), "reference_id": ref_id, "target_height": TARGET_HEIGHT, "semantic": semantic,
               "report": str(d / "analysis.json")}
        report = self._blender(d / "source.blend", "build", job, d / "build.log")
        if report.get("status") == "ok" and not (d / "semantic.yaml").is_file():
            (d / "semantic.suggested.yaml").write_text(suggest_semantic(report), encoding="utf-8")
        return report

    def extract_template(self, ref_id: str, template_id: str, kind: str = "body", title: str = "") -> dict[str, Any]:
        """Production template from a reference — only when its licence allows it."""
        d = self.ref_dir(ref_id)
        meta = self.metadata(ref_id)
        usage = meta.get("usage") or {}
        if not (usage.get("derivative_allowed") is True and usage.get("production_template_allowed") is True):
            raise ReferenceLabError(
                f"reference {ref_id}: usage.derivative_allowed and usage.production_template_allowed must both be "
                "true in reference.yaml (set by a human after checking the licence); the reference stays "
                "visual/topology study only")
        if kind not in TEMPLATE_KINDS:
            raise ReferenceLabError(f"template kind must be one of {', '.join(TEMPLATE_KINDS)}")
        semantic = _read_yaml(d / "semantic.yaml")
        if not semantic:
            raise ReferenceLabError(f"reference {ref_id}: write semantic.yaml first (see semantic.suggested.yaml)")
        normalized = d / "normalized" / "normalized.blend"
        if not normalized.is_file():
            raise ReferenceLabError(f"reference {ref_id}: run `reference build {ref_id}` first")
        out = self.templates / kind / template_id
        out.mkdir(parents=True, exist_ok=True)
        provenance = {"reference": ref_id, "title": meta.get("title", ""), "author": meta.get("author", ""),
                      "source_url": meta.get("source_url", ""), "license": meta.get("license", ""),
                      "usage": usage, "source_sha256": _sha256(d / "source.blend"),
                      "normalized_sha256": _sha256(normalized)}
        job = {"ref_dir": str(d), "reference_id": ref_id, "template_id": template_id, "kind": kind,
               "title": title or f"{meta.get('title', ref_id)} → {kind} template", "template_dir": str(out),
               "semantic": semantic, "provenance": provenance, "report": str(out / "extract_report.json")}
        return self._blender(normalized, "template", job, out / "extract.log")
