"""Pydantic schemas for recipe files (`_base.md` frontmatter and variant YAML)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Kind = Literal["components", "assets", "materials", "characters"]
KINDS: tuple[Kind, ...] = ("components", "assets", "materials", "characters")
Status = Literal["draft", "built", "failed", "approved", "archived"]
STATUSES: tuple[Status, ...] = ("draft", "built", "failed", "approved", "archived")
Author = Literal["human", "llm"]
ParamType = Literal["int", "float", "enum", "bool", "color"]
ComponentType = Literal["part", "structure"]
StructureRelationType = Literal[
    "attached_to", "supported_by", "touches_ground", "aligned",
    "evenly_spaced", "symmetric", "mirrored", "contained_on_edge", "connected",
]
Axis = Literal["x", "y", "z", "path"]
Edge = Literal["left", "right", "front", "back", "top", "bottom"]

# Socket types (free strings, this is the documented vocabulary):
#   roof      horizontal surface, component stands on it (+Z up)
#   wall_base ground level at a wall face; local +Y points into the wall, +Z up
#   axle      rotation axis = socket local +Z (gears, wall fans)
#   surface   generic outward mount on a face: +Z points out of the surface (weapons, sensors, panels)
#   leg       hip of a walker: +Z points from the hip toward the foot, +X outward (knee side)
#   entrance  where vehicles arrive
#   ground    free ground spot
#   generic   accepts anything
GENERIC_SOCKET = "generic"

Vec3 = tuple[float, float, float]
Grid3 = tuple[int, int, int]


class ParamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ParamType
    default: Any
    min: float | None = None
    max: float | None = None
    values: list[str] | None = None
    description: str = ""
    group: str | None = None           # UI grouping only (characters: body, proportions, head, hair, …)

    @model_validator(mode="after")
    def _enum_has_values(self) -> ParamSpec:
        if self.type == "enum" and not self.values:
            raise ValueError("enum param requires non-empty `values`")
        return self


class Socket(BaseModel):
    """Attachment point. Coordinates are glTF/Godot convention: meters, +Y up.

    A mounted component is placed so that its own pivot/axes coincide with the socket frame.
    """

    name: str
    type: str = GENERIC_SOCKET
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    description: str = ""


class Interface(BaseModel):
    """Component/asset contract. grid_size is [X, Y(up), Z] in voxels."""

    grid_size: Grid3
    voxel_size: float = 0.25
    # bottom_center: stands on y=0 around the origin; ground: origin on the ground under the model,
    # geometry may hover above it (walker hulls on legs, flying units)
    pivot: Literal["bottom_center", "ground"] = "bottom_center"
    mounts: list[str] = []          # socket types this component can be mounted on ([] = any)
    sockets: list[Socket] = []      # attachment points it offers to other components

    def socket_names(self) -> list[str]:
        return [s.name for s in self.sockets]

    def socket(self, name: str) -> Socket | None:
        return next((s for s in self.sockets if s.name == name), None)


class SlotSpec(BaseModel):
    """Asset slot.

    socket=None marks the body slot. `socket: roof_left` mounts on a body socket,
    `socket: frame.gear_a` mounts on socket `gear_a` of the component in slot `frame`.
    """

    socket: str | None = None
    accepts: list[str] = []
    max_grid: Grid3
    required: bool = True
    description: str = ""


class StructuralRelation(BaseModel):
    """A measurable relationship between named mesh groups in glTF/Godot axes.

    A group is the value of ``obj['semantic_part']`` on one or more mesh objects.
    Repeated posts must be separate objects with the same group name.
    """

    model_config = ConfigDict(extra="forbid")

    type: StructureRelationType
    part: str = Field(min_length=1)
    target: str | None = None
    axis: Axis | None = None
    edge: Edge | None = None
    tolerance: float = Field(0.04, ge=0.0, le=0.0625)
    min_level: int = Field(0, ge=0, le=3)

    @model_validator(mode="after")
    def _required_fields(self) -> StructuralRelation:
        if self.type == "evenly_spaced" and "tolerance" not in self.model_fields_set:
            self.tolerance = 0.015
        if self.type in {"attached_to", "supported_by", "aligned", "contained_on_edge", "connected"} and not self.target:
            raise ValueError(f"{self.type} requires target")
        if self.type in {"aligned", "evenly_spaced", "symmetric", "mirrored"} and self.axis is None:
            raise ValueError(f"{self.type} requires axis")
        if self.axis == "path" and self.type != "evenly_spaced":
            raise ValueError("axis path is only valid for evenly_spaced")
        if self.type == "contained_on_edge" and self.edge is None:
            raise ValueError("contained_on_edge requires edge")
        return self


class DesignIntent(BaseModel):
    """Opt-in functional and structural contract for a generated component."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    primary_parts: list[str] = Field(min_length=1)
    secondary_parts: list[str] = Field(default_factory=list)
    relationships: list[StructuralRelation] = Field(default_factory=list)
    intentional_asymmetry: dict[str, str] = Field(default_factory=dict)
    forbidden: list[Literal["floating_parts", "orphan_geometry", "arbitrary_asymmetry",
                            "decorative_supports"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _known_parts(self) -> DesignIntent:
        names = [*self.primary_parts, *self.secondary_parts]
        if len(self.forbidden) != len(set(self.forbidden)):
            raise ValueError("forbidden entries must be unique")
        if len(names) != len(set(names)) or any(not name.strip() for name in names):
            raise ValueError("part names must be non-empty and unique")
        known = set(names)
        for relation in self.relationships:
            if relation.part not in known or (relation.target and relation.target not in known):
                raise ValueError(f"relationship uses undeclared part: {relation.part} -> {relation.target}")
        if any(part not in known or not reason.strip() for part, reason in self.intentional_asymmetry.items()):
            raise ValueError("intentional_asymmetry needs a declared part and a non-empty reason")
        return self


class DetailBudget(BaseModel):
    """Conservative, measurable defaults for opt-in asset composition checks."""

    model_config = ConfigDict(extra="forbid")

    max_large_attachments: int = Field(3, ge=0)
    max_repeats_per_component: int = Field(2, ge=1)
    max_roof_density: float = Field(0.5, ge=0.0, le=1.0)
    max_front_density: float = Field(0.5, ge=0.0, le=1.0)
    min_empty_socket_ratio: float = Field(0.25, ge=0.0, le=1.0)


class CompositionIntent(BaseModel):
    """Opt-in visual hierarchy for an assembled asset, separate from structure."""

    model_config = ConfigDict(extra="forbid")

    read_at_glance: str = Field(min_length=1)
    primary_mass: str = Field(min_length=1)
    # Optional envelope of the main masses when the primary component is only a frame.
    massing_grid: Grid3 | None = None
    hero_feature: str | None = None
    secondary_features: list[str] = Field(default_factory=list, max_length=2)
    quiet_zones: list[str] = Field(default_factory=list)
    detail_budget: DetailBudget = Field(default_factory=DetailBudget)
    slot_zones: dict[str, Literal["roof", "front", "side", "back", "ground"]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _positive_massing_grid(self) -> CompositionIntent:
        if self.massing_grid is not None and min(self.massing_grid) <= 0:
            raise ValueError("massing_grid dimensions must be positive")
        return self


class CharacterSpec(BaseModel):
    """Character contract: the shared rig and the clips every build must carry (see builder/humanoid.py)."""

    model_config = ConfigDict(extra="forbid")

    rig: Literal["humanoid_v1"] = "humanoid_v1"
    clips: list[str] = Field(default_factory=lambda: ["idle", "walk", "talk", "work", "celebrate"], min_length=1)


class EntityDoc(BaseModel):
    """Fully resolved entity description (inheritance applied)."""

    kind: Kind
    id: str
    title: str = ""
    type: ComponentType = "part"
    inherits: str | None = None
    abstract: bool = False
    category: str | None = None
    generator_version: int = 1
    interface: Interface | None = None
    design_intent: DesignIntent | None = None
    composition: CompositionIntent | None = None
    params: dict[str, ParamSpec] = {}
    slots: dict[str, SlotSpec] = {}
    complexity_level: int = Field(0, ge=0, le=3)
    tags: list[str] = []
    shader: str | None = None          # materials: shading model implemented by blender.py / viewer / Godot
    preview: list[str] = []            # materials: entities rendered in previews, e.g. "assets/oil_well"
    character: CharacterSpec | None = None   # characters: rig and animation clips
    chain: list[str] = []
    description: str = ""
    frontmatter: dict[str, Any] = {}

    def body_slot(self) -> str | None:
        for name, slot in self.slots.items():
            if slot.socket is None:
                return name
        return None


class VariantBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    parent: str | None = None
    level: int = Field(1, ge=0, le=3)
    author: Author = "human"
    note: str = ""
    tags: list[str] = []
    rating: int | None = Field(None, ge=1, le=5)
    status: Status = "draft"
    created: str | None = None
    # Manual geometry: a .blend next to this YAML replaces the generator (component) or the slot
    # assembly (asset) for this variant and its descendants (see backend/manual.py).
    # None = procedural, the usual case.
    source: str | None = None

    @field_validator("source")
    @classmethod
    def _source_file_name(cls, value: str | None) -> str | None:
        if value is not None and not MANUAL_SOURCE_RE.match(value):
            raise ValueError(f"source must be a file name like v004.blend, got {value!r}")
        return value


MANUAL_SOURCE_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*\.blend$")


class ComponentVariant(VariantBase):
    delta: dict[str, Any] = {}


class AssetVariant(VariantBase):
    slots: dict[str, str | None] = {}
    # Metres in asset/glTF axes: X right, Y up, Z towards the front.
    slot_offsets: dict[str, Vec3] = {}
    params_delta: dict[str, Any] = {}
    composition_delta: dict[str, Any] = {}


Variant = ComponentVariant | AssetVariant

_FIELD_ORDER = ("id", "parent", "source", "delta", "slots", "slot_offsets", "params_delta", "composition_delta", "level", "author", "note", "tags",
                "rating", "status", "created")


def variant_to_yaml_dict(variant: Variant) -> dict[str, Any]:
    data = variant.model_dump(mode="json")
    ordered = {key: data.pop(key) for key in _FIELD_ORDER if key in data}
    ordered.update(data)
    for key in ("created", "source"):  # procedural variants keep their files unchanged
        if ordered.get(key) is None:
            ordered.pop(key, None)
    return ordered


def variant_model(kind: Kind) -> type[ComponentVariant] | type[AssetVariant]:
    """Components, materials and characters are parameter deltas; assets are slot compositions."""
    return AssetVariant if kind == "assets" else ComponentVariant
