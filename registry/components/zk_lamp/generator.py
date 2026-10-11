"""Rectangular lamp mounted by its back face, local Blender +Z outward."""

from __future__ import annotations

from zuk_lamps import lamp_spec, render_lamp


def build(params):  # noqa: ANN001, ANN201
    return render_lamp(params)
