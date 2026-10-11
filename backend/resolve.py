"""Pure resolution logic: inheritance, parameter deltas, validation, hashing, slot compatibility.

Nothing here touches the filesystem — callers pass loaders/dicts, which keeps it easy to test.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import ValidationError

from .models import GENERIC_SOCKET, EntityDoc, Kind, ParamSpec, SlotSpec, VariantBase


class RecipeError(Exception):
    """One or more problems in recipe data; `errors` is a list of human-readable messages."""

    def __init__(self, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("; ".join(self.errors))


# ----------------------------------------------------------------------------- inheritance

def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge dicts; the override wins. Lists and scalars are replaced, not merged."""
    out: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


BaseLoader = Callable[[str], tuple[dict[str, Any], str]]
_NOT_INHERITED = ("abstract",)


def resolve_entity(kind: Kind, entity_id: str, load_base: BaseLoader) -> EntityDoc:
    """Walk `inherits` up to the root, merge frontmatter root→leaf and concatenate prose root→leaf."""
    metas: list[dict[str, Any]] = []
    proses: list[str] = []
    chain: list[str] = []
    current: str | None = entity_id
    while current:
        if current in chain:
            raise RecipeError(f"inheritance cycle: {' -> '.join([*chain, current])}")
        try:
            meta, prose = load_base(current)
        except FileNotFoundError as exc:
            raise RecipeError(f"{chain[-1] if chain else entity_id}: parent '{current}' not found") from exc
        chain.append(current)
        metas.append(meta)
        proses.append(prose)
        current = meta.get("inherits")

    chain.reverse()
    metas.reverse()
    proses.reverse()

    merged: dict[str, Any] = {}
    for meta in metas:
        merged = deep_merge(merged, {k: v for k, v in meta.items() if k not in _NOT_INHERITED})
    leaf = metas[-1]
    merged["id"] = entity_id
    merged["inherits"] = leaf.get("inherits")
    merged["abstract"] = bool(leaf.get("abstract", False))

    description = "\n\n".join(p.strip() for p in proses if p.strip())
    known = set(EntityDoc.model_fields) - {"kind", "chain", "description", "frontmatter"}
    try:
        return EntityDoc.model_validate({
            **{k: v for k, v in merged.items() if k in known},
            "kind": kind,
            "chain": chain,
            "description": description,
            "frontmatter": merged,
        })
    except ValidationError as exc:
        raise RecipeError([f"{entity_id}: {_fmt_pydantic(err)}" for err in exc.errors()]) from exc


def _fmt_pydantic(err: Mapping[str, Any]) -> str:
    loc = ".".join(str(p) for p in err.get("loc", ()))
    return f"{loc}: {err.get('msg')}" if loc else str(err.get("msg"))


# ----------------------------------------------------------------------------- parameters

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def coerce_value(spec: ParamSpec, value: Any) -> Any:
    """Validate a single value against its spec and return the canonical typed value."""
    if spec.type == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"expected bool, got {value!r}")
        return value
    if spec.type == "enum":
        if not isinstance(value, str) or value not in (spec.values or []):
            raise ValueError(f"expected one of {spec.values}, got {value!r}")
        return value
    if spec.type == "color":
        if not isinstance(value, str) or not _COLOR_RE.match(value):
            raise ValueError(f"expected color #rrggbb, got {value!r}")
        return value.lower()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected {spec.type}, got {value!r}")
    if spec.type == "int":
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError(f"expected int, got {value!r}")
            value = int(value)
        number: float = value
    else:
        if not math.isfinite(value):
            raise ValueError(f"expected finite float, got {value!r}")
        number = round(float(value), 9) + 0.0  # + 0.0 folds -0.0 into 0.0
        value = number
    if spec.min is not None and number < spec.min:
        raise ValueError(f"{value} < min {spec.min:g}")
    if spec.max is not None and number > spec.max:
        raise ValueError(f"{value} > max {spec.max:g}")
    return value


def validate_params(schema: Mapping[str, ParamSpec], values: Mapping[str, Any], *,
                    partial: bool = False) -> tuple[dict[str, Any], list[str]]:
    """Return (clean values, errors). With partial=True missing keys are allowed (for deltas)."""
    clean: dict[str, Any] = {}
    errors: list[str] = []
    for key, value in values.items():
        spec = schema.get(key)
        if spec is None:
            errors.append(f"{key}: unknown parameter")
            continue
        try:
            clean[key] = coerce_value(spec, value)
        except ValueError as exc:
            errors.append(f"{key}: {exc}")
    if not partial:
        errors.extend(f"{key}: missing" for key in schema if key not in values)
    return clean, errors


def validate_schema_defaults(schema: Mapping[str, ParamSpec]) -> list[str]:
    _, errors = validate_params(schema, {k: s.default for k, s in schema.items()})
    return [f"default {e}" for e in errors]


def variant_chain(variants: Mapping[str, VariantBase], vid: str) -> list[VariantBase]:
    """Variants from the root to `vid` (inclusive)."""
    chain: list[VariantBase] = []
    seen: set[str] = set()
    current: str | None = vid
    while current is not None:
        if current in seen:
            raise RecipeError(f"variant cycle at {current}")
        variant = variants.get(current)
        if variant is None:
            raise RecipeError(f"variant '{current}' not found" + (f" (parent of {chain[-1].id})" if chain else ""))
        seen.add(current)
        chain.append(variant)
        current = variant.parent
    chain.reverse()
    return chain


def resolve_params(schema: Mapping[str, ParamSpec], deltas: list[tuple[str, Mapping[str, Any]]]
                   ) -> tuple[dict[str, Any], dict[str, str]]:
    """Schema defaults ← deltas in chain order. Returns (params, source of each value).

    `deltas` is [(variant_id, delta), ...] ordered root → leaf.
    """
    values: dict[str, Any] = {key: spec.default for key, spec in schema.items()}
    sources: dict[str, str] = {key: "default" for key in schema}
    errors: list[str] = []
    for vid, delta in deltas:
        for key, value in delta.items():
            if key not in schema:
                errors.append(f"{vid}: {key}: unknown parameter")
                continue
            values[key] = value
            sources[key] = vid
    clean, value_errors = validate_params(schema, values)
    errors.extend(f"{sources.get(e.split(':', 1)[0], '?')}: {e}" for e in value_errors)
    if errors:
        raise RecipeError(errors)
    return clean, sources


# ----------------------------------------------------------------------------- hashing

def _normalize(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("non-finite float in recipe")
        return round(obj, 9) + 0.0
    if isinstance(obj, Mapping):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(_normalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def build_hash(generator_version: str, resolved: Any) -> str:
    """sha256(generator_version + canonical_json(resolved)), shortened to 16 hex chars."""
    payload = f"{generator_version}\n{canonical_json(resolved)}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


# ----------------------------------------------------------------------------- slots

def parse_slot_ref(ref: str) -> tuple[str, str]:
    component, sep, vid = ref.partition("@")
    if not sep or not component or not vid:
        raise RecipeError(f"bad slot reference '{ref}', expected component@variant")
    return component.strip(), vid.strip()


def parse_entity_slot_ref(ref: str) -> tuple[str, str, str]:
    """Resolve explicit component/asset refs while keeping legacy component@variant syntax."""
    entity, vid = parse_slot_ref(ref)
    if "/" not in entity:
        return "components", entity, vid
    kind, sep, entity_id = entity.partition("/")
    if not sep or kind not in ("components", "assets") or not entity_id or "/" in entity_id:
        raise RecipeError(f"bad slot reference '{ref}', expected components/id@variant or assets/id@variant")
    return kind, entity_id, vid


def split_socket_path(path: str, body_slot: str) -> tuple[str, str]:
    """`roof_left` → (body_slot, roof_left); `frame.gear_a` → (frame, gear_a)."""
    host, sep, socket = path.partition(".")
    if not sep:
        return body_slot, path
    if not host or not socket:
        raise RecipeError(f"bad socket path '{path}', expected <slot>.<socket>")
    return host, socket


MAX_SLOT_OFFSET_M = 10.0


def validate_slot_offsets(offsets: Mapping[str, Any], slot_names: Mapping[str, SlotSpec]
                          ) -> tuple[dict[str, tuple[float, float, float]], list[str]]:
    """Canonicalize asset-space XYZ translations; reject unknown or unbounded placements."""
    clean: dict[str, tuple[float, float, float]] = {}
    errors: list[str] = []
    for name, value in offsets.items():
        if name not in slot_names:
            errors.append(f"unknown slot '{name}' in slot_offsets")
            continue
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            errors.append(f"slot_offsets.{name}: expected [x, y, z]")
            continue
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
            errors.append(f"slot_offsets.{name}: coordinates must be numbers")
            continue
        numbers = tuple(round(float(v), 9) + 0.0 for v in value)
        if any(not math.isfinite(v) for v in numbers):
            errors.append(f"slot_offsets.{name}: coordinates must be finite")
        elif any(abs(v) > MAX_SLOT_OFFSET_M for v in numbers):
            errors.append(f"slot_offsets.{name}: each coordinate must be within ±{MAX_SLOT_OFFSET_M:g} m")
        else:
            clean[name] = numbers
    return clean, errors


def slot_accepts(slot: SlotSpec, component: EntityDoc) -> bool:
    """`accepts` matches id, category, type or qualified kind/id; empty = anything."""
    return not slot.accepts or bool({component.id, component.category, component.type,
                                     f"{component.kind}/{component.id}"} & set(slot.accepts))


def slot_compatibility(slot_name: str, slot: SlotSpec, component: EntityDoc,
                       host: EntityDoc | None = None, socket: str | None = None) -> list[str]:
    """Reasons why `component` cannot go into `slot` (empty list = compatible).

    `host` is the component that owns the target socket (body or a structure in another slot).
    """
    reasons: list[str] = []
    if component.kind not in ("components", "assets"):
        reasons.append(f"{component.id} is not a component or asset")
    if component.abstract:
        reasons.append(f"{component.id} is abstract")
    if not slot_accepts(slot, component):
        reasons.append(f"slot '{slot_name}' accepts {slot.accepts}, got {component.id}"
                       f" ({component.category or '-'}, {component.type})")
    if component.interface is None:
        reasons.append(f"{component.id} has no interface")
    else:
        grid = component.interface.grid_size
        if any(c > m for c, m in zip(grid, slot.max_grid)):
            reasons.append(f"grid {list(grid)} exceeds slot max_grid {list(slot.max_grid)}")
    if socket is not None and host is not None:
        target = host.interface.socket(socket) if host.interface else None
        if target is None:
            reasons.append(f"{host.id} has no socket '{socket}'")
        elif component.interface is not None:
            mounts = component.interface.mounts
            if mounts and target.type != GENERIC_SOCKET and target.type not in mounts:
                reasons.append(f"{component.id} mounts on {mounts}, socket {host.id}.{socket} is '{target.type}'")
    return reasons
