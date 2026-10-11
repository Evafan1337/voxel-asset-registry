"""Check workflow boundaries, edit invariants and non-destructive saved requests."""

import json
from pathlib import Path

import pytest
import yaml

from impressor.sketch import PROJECTION_CONTRACT, compile_sketch, prepare_sketch


EXAMPLE = Path(__file__).resolve().parents[1] / "impressor/templates/sketch_brief.example.yaml"


def brief_file(tmp_path, **changes):
    brief = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    brief["template"] = str(EXAMPLE.parent / "sketch_template.yaml")
    brief.update(changes)
    result = tmp_path / "brief.yaml"
    result.write_text(yaml.safe_dump(brief, allow_unicode=True), encoding="utf-8")
    return result


def test_cube_request_uses_only_supported_tool_arguments():
    _, _, request = compile_sketch(EXAMPLE)
    assert set(request) == {"prompt", "transparent_background"}
    assert "ONLY cubes and rectangular cuboids" in request["prompt"]
    assert "box placeholders" in request["prompt"]
    assert "no textures or colored accents" in request["prompt"]


def test_projection_sheet_uses_one_object_envelope_and_all_seven_fixed_views():
    brief, _, request = compile_sketch(EXAMPLE)
    assert brief["view_mode"] == "projection_sheet"
    assert brief["view_contract"] == PROJECTION_CONTRACT
    assert brief["dimensions"]["envelope_m"] == [1.25, 1.5, 3.0]
    prompt = request["prompt"]
    assert "First row, left to right: front, rear, left, right" in prompt
    assert "Second row: top, bottom, isometric, empty cell" in prompt
    assert "strict orthographic projections" in prompt
    assert "same orthographic pixels-per-meter scale" in prompt
    assert "identical dimensions, gaps, part counts" in prompt
    assert "[X=1.25, Y=1.5, Z=3]" in prompt
    assert "ground is Y=0" in prompt
    assert "verified against projections rendered from one real 3D blockout" in prompt
    assert "No collage" not in prompt


@pytest.mark.parametrize("dimensions", [
    None,
    {"units": "voxels", "axes": "gltf_y_up", "envelope_m": [1, 2, 3], "ground_y_m": 0},
    {"units": "meters", "axes": "blender_z_up", "envelope_m": [1, 2, 3], "ground_y_m": 0},
    {"units": "meters", "axes": "gltf_y_up", "envelope_m": [1, 2], "ground_y_m": 0},
    {"units": "meters", "axes": "gltf_y_up", "envelope_m": [1, 0, 3], "ground_y_m": 0},
    {"units": "meters", "axes": "gltf_y_up", "envelope_m": [1, True, 3], "ground_y_m": 0},
    {"units": "meters", "axes": "gltf_y_up", "envelope_m": [1, float("nan"), 3], "ground_y_m": 0},
    {"units": "meters", "axes": "gltf_y_up", "envelope_m": [1, 2, 3], "ground_y_m": float("inf")},
])
def test_projection_sheet_rejects_unknown_units_axes_or_invalid_dimensions(tmp_path, dimensions):
    with pytest.raises(ValueError):
        compile_sketch(brief_file(tmp_path, dimensions=dimensions))


def test_projection_contract_cannot_drop_a_view_or_change_its_axes(tmp_path):
    for contract in (
        {**PROJECTION_CONTRACT, "orthographic_views": ["front", "top"]},
        {**PROJECTION_CONTRACT, "front_axis": "-Z"},
    ):
        with pytest.raises(ValueError, match="view_contract"):
            compile_sketch(brief_file(tmp_path, view_contract=contract))


@pytest.mark.parametrize("view_mode", ["perspective", []])
def test_unknown_view_mode_is_rejected(tmp_path, view_mode):
    with pytest.raises(ValueError, match="view_mode"):
        compile_sketch(brief_file(tmp_path, view_mode=view_mode))


def test_explicit_single_view_does_not_need_a_projection_envelope(tmp_path):
    brief, _, request = compile_sketch(brief_file(tmp_path, view_mode="single", dimensions=None))
    assert brief["view_mode"] == "single"
    assert "One object, entirely visible" in request["prompt"]
    assert "No collage or alternative views" in request["prompt"]
    assert "View contract:" not in request["prompt"]


def test_historical_single_view_run_recompiles_without_changing_its_saved_request():
    run = EXAMPLE.parents[1] / "examples/truck_cube_r001"
    _, _, request = compile_sketch(run / "brief.resolved.yaml")
    assert request == json.loads((run / "imagegen_request.json").read_text())


@pytest.mark.parametrize("changes", [{"masses": []}, {"pass": "finished"}, {"proportions": "wide"}])
def test_incomplete_or_invalid_brief_is_rejected(tmp_path, changes):
    with pytest.raises(ValueError):
        compile_sketch(brief_file(tmp_path, **changes))


def test_edit_requires_source_and_explicit_invariants(tmp_path):
    with pytest.raises(ValueError, match="change requires source_image"):
        compile_sketch(brief_file(tmp_path, change="Lower the cab"))
    (tmp_path / "previous.png").write_bytes(b"image placeholder")
    with pytest.raises(ValueError, match="invariants"):
        compile_sketch(brief_file(tmp_path, source_image="previous.png", preserve=[], change="Lower the cab"))


def test_edit_resolves_source_relative_to_brief(tmp_path):
    source = tmp_path / "previous.png"
    source.write_bytes(b"image placeholder")
    _, _, request = compile_sketch(brief_file(tmp_path, source_image="previous.png", change="Lower only the cab", **{"pass": "silhouette"}))
    assert request["referenced_image_paths"] == [str(source)]
    assert "Change only this: Lower only the cab" in request["prompt"]
    assert "ONLY cubes" not in request["prompt"]
    assert "num_last_images_to_include" not in request


def test_run_is_prepared_without_claiming_generated_image_and_cannot_overwrite(tmp_path):
    output = tmp_path / "r001"
    prepare_sketch(EXAMPLE, output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "prepared"
    assert manifest["image"] is None
    assert manifest["view_mode"] == "projection_sheet"
    assert manifest["view_contract"] == PROJECTION_CONTRACT
    assert manifest["dimensions"]["envelope_m"] == [1.25, 1.5, 3.0]
    assert (output / "brief.resolved.yaml").exists()
    assert (output / "template.resolved.yaml").exists()
    request = json.loads((output / "imagegen_request.json").read_text())
    assert (output / "prompt.txt").read_text() == request["prompt"]
    with pytest.raises(FileExistsError):
        prepare_sketch(EXAMPLE, output)


def test_edit_run_preserves_input_and_can_recompile_its_snapshot(tmp_path):
    source = tmp_path / "previous.png"
    source.write_bytes(b"accepted original image")
    output = tmp_path / "r002"
    prepare_sketch(brief_file(tmp_path, source_image="previous.png", change="Lower only the cab"), output)
    source.write_bytes(b"later external change")
    manifest = json.loads((output / "manifest.json").read_text())
    assert (output / manifest["source_image"]["path"]).read_bytes() == b"accepted original image"
    assert manifest["source_image"]["sha256"]
    request = json.loads((output / "imagegen_request.json").read_text())
    _, _, recompiled = compile_sketch(output / "brief.resolved.yaml")
    assert recompiled == request
