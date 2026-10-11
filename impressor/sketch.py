"""Compile a sketch brief and shared template into a built-in ImageGen request."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from string import Template

import yaml


PROMPT_TEMPLATE = Path(__file__).parent / "templates" / "sketch_prompt.template.txt"
PASSES = {"cube_massing", "silhouette", "structure", "detail", "game_check"}
ORTHOGRAPHIC_VIEWS = ["front", "rear", "left", "right", "top", "bottom"]
PROJECTION_CONTRACT = {
    "schema": "impressor/projections/v1",
    "axes": "gltf_y_up",
    "front_axis": "+Z",
    "orthographic_views": ORTHOGRAPHIC_VIEWS,
    "angled_view": "isometric",
    "layout": "rows_of_four",
}


def _mapping(path: Path, schema: str) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise ValueError(f"{path}: expected schema {schema}")
    return value


def _text(value: dict, key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{key}: expected nonempty text")
    return result.strip()


def _items(value: dict, key: str, *, required: bool = False) -> list[str]:
    result = value.get(key, [])
    if not isinstance(result, list) or any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{key}: expected a list of nonempty strings")
    if required and not result:
        raise ValueError(f"{key}: provide at least one item")
    return [item.strip() for item in result]


def _number(value: object, key: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key}: expected a finite number")
    if positive and value <= 0:
        raise ValueError(f"{key}: expected a positive number")
    return float(value)


def _views(brief: dict, template: dict) -> tuple[str, str]:
    """Resolve view rules; legacy saved templates keep their original single view."""
    mode = brief.get("view_mode", template.get("view_mode", "single"))
    if not isinstance(mode, str) or mode not in {"single", "projection_sheet"}:
        raise ValueError("view_mode: expected single or projection_sheet")
    brief["view_mode"] = mode
    if mode == "single":
        return _text(template, "single_composition" if "single_composition" in template else "composition"), ""

    contract = brief.get("view_contract", template.get("view_contract", PROJECTION_CONTRACT))
    if not isinstance(contract, dict) or contract != PROJECTION_CONTRACT:
        raise ValueError("view_contract: expected impressor/projections/v1 with all six orthographic views and isometric")
    dimensions = brief.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("dimensions: projection_sheet requires a numeric envelope and ground plane")
    if dimensions.get("units") != "meters" or dimensions.get("axes") != "gltf_y_up":
        raise ValueError("dimensions: use units meters and axes gltf_y_up")
    envelope = dimensions.get("envelope_m")
    if not isinstance(envelope, list) or len(envelope) != 3:
        raise ValueError("envelope_m: expected [X width, Y height, Z depth]")
    width, height, depth = [_number(item, "envelope_m", positive=True) for item in envelope]
    ground = _number(dimensions.get("ground_y_m"), "ground_y_m")
    brief["dimensions"] = {
        "units": "meters", "axes": "gltf_y_up",
        "envelope_m": [width, height, depth], "ground_y_m": ground,
    }
    # Store the entire contract in the run, rather than only an external template reference.
    brief["view_contract"] = {**PROJECTION_CONTRACT, "orthographic_views": list(ORTHOGRAPHIC_VIEWS)}
    composition = (
        "One projection sheet of the SAME object, with seven views in a fixed two-row, "
        "four-column grid. First row, left to right: front, rear, left, right. "
        "Second row: top, bottom, isometric, empty cell. Exactly one object instance "
        "per occupied cell, entirely visible with clear margins; no alternatives or extra panels."
    )
    view_line = (
        "View contract: impressor/projections/v1. Use glTF/Godot axes: +Y up, +Z front, "
        "+X right. Front/rear cameras are on +Z/-Z, left/right on -X/+X, top/bottom "
        "on +Y/-Y, looking toward the object center. All six are strict orthographic "
        "projections, with no perspective convergence or visible adjacent faces. "
        "Keep +Y up in front/rear/side panels; in top/bottom panels, keep +Z toward "
        "the top of the sheet: +X appears left in top and right in bottom. "
        "The separate angled view is true orthographic isometric, from +X,+Y,+Z, "
        "roughly 35.264 degrees elevation and 45 degrees around the vertical axis. "
        f"One shared envelope in meters is [X={width:g}, Y={height:g}, Z={depth:g}]; "
        f"ground is Y={ground:g}, bottom-center origin is (0,{ground:g},0). "
        "Use the same orthographic pixels-per-meter scale for all six panels; do not "
        "independently stretch or normalize each view to its cell. Derive every view "
        "from one shared arrangement of the named masses: identical dimensions, gaps, "
        "part counts, symmetry, contact points and ground plane. Occlusion may hide "
        "a part; never invent or remove a part to improve an individual panel. "
        "Use light flat plane shading in the orthographic views, without cast shadows "
        "that obscure boundaries; a subtle contact shadow is allowed only in isometric. "
        "These generated views remain a visual hypothesis: geometric consistency and "
        "measurements must be verified against projections rendered from one real 3D blockout."
    )
    return composition, view_line


def compile_sketch(brief_path: Path) -> tuple[dict, dict, dict]:
    """Return resolved brief, template and tool arguments; never render an image."""
    brief_path = brief_path.resolve()
    brief = _mapping(brief_path, "impressor/sketch/v1")
    run_id = _text(brief, "id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", run_id):
        raise ValueError("id: use lowercase letters, numbers, underscores or hyphens")
    pass_name = _text(brief, "pass")
    if pass_name not in PASSES:
        raise ValueError(f"Unsupported pass: {pass_name}")
    template_path = (brief_path.parent / _text(brief, "template")).resolve()
    template = _mapping(template_path, "impressor/sketch-template/v1")
    _text(template, "id")
    passes = template.get("passes")
    if not isinstance(passes, dict):
        raise ValueError("passes: expected a mapping of pass names to rules")
    rules = passes.get(pass_name)
    if not isinstance(rules, dict):
        raise ValueError(f"Template has no rules for pass {pass_name}")

    masses = _items(brief, "masses", required=True)
    proportions = _items(brief, "proportions", required=True)
    preserve = _items(brief, "preserve")
    avoid = _items(template, "avoid") + _items(rules, "avoid") + _items(brief, "avoid")
    geometry = _text(rules, "geometry")
    materials = _text(rules, "materials")
    constraints = _items(template, "constraints", required=True)
    composition, view_line = _views(brief, template)
    # These workflow invariants survive customization of the shared template.
    if pass_name == "cube_massing":
        geometry = "ONLY cubes and rectangular cuboids with orthogonal faces. " + geometry
        materials = "Uniform neutral matte grey; no textures or colored accents."
        constraints.append("Use box placeholders for every curved part, including wheels; no curved geometry.")
        avoid += ["cylinders, spheres, wedges, bevels, round wheels", "windows, panel seams, bolts, lamps, decals, textures"]

    source = brief.get("source_image")
    input_line = ""
    edit_line = ""
    reference_paths = []
    if source is not None:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source_image: expected a path or null")
        source_path = (brief_path.parent / source).resolve()
        if not source_path.is_file():
            raise ValueError(f"Source image does not exist: {source_path}")
        if not preserve:
            raise ValueError("preserve: edits must explicitly list their invariants")
        change = _text(brief, "change")
        reference_paths.append(str(source_path))
        brief["source_image"] = str(source_path)
        input_line = "Input images: Image 1 is the edit target, the accepted previous sketch."
        edit_line = f"Edit instruction: Change only this: {change}. Preserve: {'; '.join(preserve)}."
    elif brief.get("change"):
        raise ValueError("change requires source_image; a text-only rerun is not a preserved-image edit")
    else:
        constraints += [f"Preserve: {item}" for item in preserve]

    prompt = Template(PROMPT_TEMPLATE.read_text(encoding="utf-8")).substitute(
        subject=_text(brief, "subject"), purpose=_text(brief, "purpose"),
        question=_text(brief, "question"), pass_name=pass_name,
        background=_text(template, "background"), style=_text(template, "style"),
        composition=composition, lighting=_text(template, "lighting"), view_line=view_line,
        masses="\n".join(f"- {item}" for item in masses),
        proportions="; ".join(proportions), geometry=geometry, materials=materials,
        constraints="; ".join(constraints), avoid="; ".join(avoid),
        input_line=input_line, edit_line=edit_line,
    )
    prompt = "\n".join(line for line in prompt.splitlines() if line.strip()) + "\n"
    brief["template"] = "template.resolved.yaml"
    request = {"prompt": prompt, "transparent_background": False}
    if reference_paths:
        request["referenced_image_paths"] = reference_paths
    return brief, template, request


def prepare_sketch(brief_path: Path, output: Path) -> Path:
    """Write a new reviewable run, keeping previous outputs intact."""
    brief, template, request = compile_sketch(brief_path)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_record = None
    if request.get("referenced_image_paths"):
        source = Path(request["referenced_image_paths"][0])
        saved_source = output / f"source_image{source.suffix}"
        shutil.copy2(source, saved_source)
        brief["source_image"] = saved_source.name
        request["referenced_image_paths"] = [str(saved_source)]
        source_record = {"path": saved_source.name, "sha256": hashlib.sha256(saved_source.read_bytes()).hexdigest()}
    (output / "prompt.txt").write_text(request["prompt"], encoding="utf-8")
    (output / "imagegen_request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, value in (("brief.resolved.yaml", brief), ("template.resolved.yaml", template)):
        (output / name).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
    manifest = {
        "schema": "impressor/sketch-run/v1", "id": brief["id"], "pass": brief["pass"],
        "view_mode": brief["view_mode"],
        "status": "prepared", "mode": "built_in_via_agent",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "prompt_sha256": hashlib.sha256(request["prompt"].encode()).hexdigest(),
        "image": None, "review": {"status": "pending", "observations": []},
    }
    if brief["view_mode"] == "projection_sheet":
        manifest["view_contract"] = brief["view_contract"]
        manifest["dimensions"] = brief["dimensions"]
    if source_record:
        manifest["source_image"] = source_record
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
