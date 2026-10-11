"""Turns (kind, entity, variant) into resolved parameters, a build hash and a builder recipe."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import Config
from .models import (AssetVariant, CharacterSpec, ComponentVariant, CompositionIntent, EntityDoc, Kind, SlotSpec,
                     Variant)
from .resolve import (
    RecipeError,
    build_hash,
    deep_merge,
    parse_entity_slot_ref,
    resolve_params,
    slot_compatibility,
    split_socket_path,
    validate_params,
    validate_schema_defaults,
    validate_slot_offsets,
    variant_chain,
)
from .store import Store

# Bump when builder/ changes what ends up in model.glb / report.json (export settings, checks,
# assembly rules). It is part of every build hash, so all variants get rebuilt.
BUILDER_VERSION = 5  # 5: semantic structure checks and composition-aware reports


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "builder" / "character_templates"


def _template_digest(kind: str, template_id: str) -> str:
    path = TEMPLATES_DIR / kind / template_id / "template.json"
    if not path.is_file():
        raise RecipeError(f"character template {kind}/{template_id} not found ({path.relative_to(TEMPLATES_DIR.parent.parent)})"
                          " — extract it with `python -m registry template extract`")
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@dataclass
class ComponentResolution:
    entity: EntityDoc
    variant: ComponentVariant
    chain: list[str]
    params: dict[str, Any]
    sources: dict[str, str]
    changed: list[str]
    hash: str
    models: list[dict[str, Any]] = field(default_factory=list)   # materials: preview models
    source: ManualSource | None = None                            # manual .blend geometry
    finish: dict[str, Any] | None = None

    @property
    def ref(self) -> str:
        return f"{self.entity.id}@{self.variant.id}"


@dataclass
class ManualSource:
    """The .blend that replaces generator.py; `variant` is the chain member that declared it."""

    variant: str
    path: Path
    sha256: str

    def payload(self) -> dict[str, str]:
        return {"variant": self.variant, "sha256": self.sha256}


@dataclass
class SlotResolution:
    name: str
    spec: SlotSpec
    ref: str | None
    source: str
    host: str | None = None          # slot that owns the target socket (None for the body)
    socket: str | None = None        # socket name on the host
    component: ComponentResolution | AssetResolution | None = None
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)  # glTF asset axes, metres
    offset_source: str = "default"


@dataclass
class AssetResolution:
    entity: EntityDoc
    variant: AssetVariant
    chain: list[str]
    params: dict[str, Any]
    sources: dict[str, str]
    changed: list[str]
    slots: dict[str, SlotResolution]
    changed_slots: list[str]
    changed_offsets: list[str]
    hash: str
    composition: CompositionIntent | None = None
    composition_report: dict[str, Any] | None = None
    source: ManualSource | None = None      # manual .blend of the whole composition
    finish: dict[str, Any] | None = None


Resolution = ComponentResolution | AssetResolution


@dataclass
class Plan:
    kind: Kind
    entity_id: str
    vid: str
    hash: str
    recipe: dict[str, Any]
    resolution: Resolution = field(repr=False)


class Planner:
    """Short-lived resolver with per-instance caches (create one per request / CLI run)."""

    def __init__(self, store: Store, cfg: Config):
        self.store = store
        self.cfg = cfg
        self._entities: dict[tuple[Kind, str], EntityDoc] = {}
        self._variants: dict[tuple[Kind, str], dict[str, Variant]] = {}
        self._components: dict[tuple[str, str, str], ComponentResolution] = {}
        self._assets: dict[tuple[str, str], AssetResolution] = {}
        self._resolving_assets: list[tuple[str, str]] = []
        self._finishes: dict[str, dict[str, Any]] = {}
        self._asset_hash_payloads: dict[tuple[str, str], dict[str, Any]] = {}

    # ------------------------------------------------------------------ cached loads
    def entity(self, kind: Kind, entity_id: str) -> EntityDoc:
        key = (kind, entity_id)
        if key not in self._entities:
            if not self.store.has_entity(kind, entity_id):
                raise RecipeError(f"{kind}/{entity_id} not found")
            doc = self.store.resolve(kind, entity_id)
            errors = validate_schema_defaults(doc.params)
            if errors:
                raise RecipeError([f"{entity_id}: {e}" for e in errors])
            self._entities[key] = doc
        return self._entities[key]

    def variants(self, kind: Kind, entity_id: str) -> dict[str, Variant]:
        key = (kind, entity_id)
        if key not in self._variants:
            self._variants[key], _ = self.store.variants(kind, entity_id)
        return self._variants[key]

    def forget_variants(self, kind: Kind, entity_id: str) -> None:
        self._variants.pop((kind, entity_id), None)
        self._components = {k: v for k, v in self._components.items() if (k[0], k[1]) != (kind, entity_id)}
        self._assets.clear()
        self._asset_hash_payloads.clear()

    def _finish(self, params: dict[str, Any]) -> dict[str, Any] | None:
        if "material_preset" not in params:
            return None
        name = params["material_preset"]
        if not isinstance(name, str):
            raise RecipeError("material_preset must be a preset name")
        if name not in self._finishes:
            self._finishes[name] = self.store.material_preset(name)
        finish = self._finishes[name]
        if params.get("metal_texture", "none") != "none":
            from builder.metal_texture import settings
            try:
                texture = settings(params["metal_texture"], params.get("texture_strength", .035),
                                   params.get("texture_density", 32.0), params.get("texture_seed", 13))
            except (ValueError, TypeError) as exc:
                raise RecipeError(f"metal texture: {exc}") from exc
            key = "texture_" + build_hash("metal-texture-v1", {"finish": finish, "texture": texture})
            if key not in self._finishes:
                self._finishes[key] = {**finish, "texture_key": key,
                    "materials": {color: {**props, **({"texture": texture} if props["metallic"] > 0 else {})}
                                  for color, props in finish["materials"].items()}}
            return self._finishes[key]
        return finish

    # ------------------------------------------------------------------ components
    def resolve_component(self, entity_id: str, vid: str, kind: Kind = "components") -> ComponentResolution:
        key = (kind, entity_id, vid)
        if key in self._components:
            return self._components[key]
        entity = self.entity(kind, entity_id)
        if entity.abstract:
            raise RecipeError(f"{kind}/{entity_id} is abstract")
        chain = variant_chain(self.variants(kind, entity_id), vid)
        variants = [v for v in chain if isinstance(v, ComponentVariant)]
        params, sources = resolve_params(entity.params, [(v.id, v.delta) for v in variants])
        leaf = variants[-1]
        # interface is hashed too: grid_size / sockets change the check results in report.json
        interface = entity.interface.model_dump(mode="json") if entity.interface else None
        payload: dict[str, Any] = {"params": params, "level": leaf.level, "interface": interface}
        finish = self._finish(params) if kind == "components" else None
        if finish is not None:
            payload["material_preset"] = finish
        # Design intent changes structural checks in the build report. Legacy components
        # keep their exact previous payload and hash when no intent is declared.
        if entity.design_intent is not None:
            payload["design_intent"] = entity.design_intent.model_dump(mode="json")
        if kind == "characters":
            payload["character"] = (entity.character or CharacterSpec()).model_dump(mode="json")
            template = params.get("body_template")
            if template and template != "procedural":
                # the authored mesh is geometry: every change of template.json is a new artifact
                payload["templates"] = {f"body/{template}": _template_digest("body", str(template))}
        source = self._manual_source(kind, entity_id, variants)
        if source is not None:
            # The file content is the geometry, so every save gets its own artifact.
            payload["source"] = source.payload()
        models: list[dict[str, Any]] = []
        if kind == "materials":
            models = self.preview_models(entity)
            payload = {"params": params, "level": leaf.level, "shader": entity.shader,
                       "models": [m["hash"] for m in models]}
        digest = build_hash(f"{kind}/{entity_id}@{entity.generator_version}+b{BUILDER_VERSION}", payload)
        res = ComponentResolution(entity, leaf, [v.id for v in variants], params, sources,
                                  sorted(leaf.delta), digest, models, source, finish)
        self._components[key] = res
        return res

    def _manual_source(self, kind: Kind, entity_id: str, chain: list[Variant]) -> ManualSource | None:
        """The nearest `source:` up the chain. Parameters, slots and offsets stop affecting
        geometry below it."""
        index = next((i for i in range(len(chain) - 1, -1, -1) if chain[i].source), None)
        if index is None:
            return None
        owner = chain[index]
        assert owner.source is not None
        if kind in ("materials", "characters"):
            raise RecipeError(f"{kind}/{entity_id}@{owner.id}: source is only supported for components and assets")

        def edits(v: Variant) -> list[str]:
            if isinstance(v, ComponentVariant):
                return sorted(v.delta)
            return [name for name in ("slots", "slot_offsets", "params_delta", "composition_delta")
                    if getattr(v, name)]

        errors = [f"{v.id}: {', '.join(edits(v))} has no effect on manual geometry from {owner.id} "
                  f"(branch from a procedural variant to change it)"
                  for v in chain[index:] if edits(v)]
        if errors:
            raise RecipeError(errors)
        path = self.store.source_path(kind, entity_id, owner.source)
        if not path.is_file():
            raise RecipeError(f"{kind}/{entity_id}@{owner.id}: source file {owner.source} not found")
        return ManualSource(owner.id, path, hashlib.sha256(path.read_bytes()).hexdigest())

    def preview_models(self, entity: EntityDoc) -> list[dict[str, Any]]:
        """Find built models: a pinned kind/id/variant, or approved/newest kind/id."""
        found: list[dict[str, Any]] = []
        for ref in entity.preview:
            pieces = ref.split("/")
            if len(pieces) not in (2, 3):
                continue
            kind, eid = pieces[:2]
            if kind not in ("components", "assets") or not self.store.has_entity(kind, eid):  # type: ignore[arg-type]
                continue
            available = self.variants(kind, eid)  # type: ignore[arg-type]
            if len(pieces) == 3:
                pinned = available.get(pieces[2])
                variants = [pinned] if pinned is not None else []
            else:
                variants = sorted(available.values(),
                                  key=lambda v: (v.status == "approved", v.id), reverse=True)
            for v in variants:
                if v.status == "archived":
                    continue
                try:
                    digest = self.resolve(kind, eid, v.id).hash  # type: ignore[arg-type]
                except RecipeError:
                    continue
                artifact_dir = self.cfg.build_dir / digest
                report = artifact_dir / "report.json"
                model = artifact_dir / "model.glb"
                if not model.is_file():
                    continue
                try:
                    result = json.loads(report.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if result.get("status") == "ok":
                    found.append({"ref": f"{kind}/{eid}@{v.id}", "hash": digest,
                                  "glb": str(model)})
                    break
        return found

    # ------------------------------------------------------------------ assets
    def resolve_asset(self, entity_id: str, vid: str) -> AssetResolution:
        key = (entity_id, vid)
        if key in self._assets:
            return self._assets[key]
        if key in self._resolving_assets:
            chain = [*self._resolving_assets, key]
            raise RecipeError("asset composition cycle: " + " -> ".join(f"{eid}@{v}" for eid, v in chain))
        self._resolving_assets.append(key)
        try:
            result = self._resolve_asset_uncached(entity_id, vid)
            self._assets[key] = result
            return result
        finally:
            self._resolving_assets.pop()

    def _resolve_asset_uncached(self, entity_id: str, vid: str) -> AssetResolution:
        entity = self.entity("assets", entity_id)
        if entity.abstract:
            raise RecipeError(f"assets/{entity_id} is abstract")
        chain = [v for v in variant_chain(self.variants("assets", entity_id), vid) if isinstance(v, AssetVariant)]
        params, sources = resolve_params(entity.params, [(v.id, v.params_delta) for v in chain])
        finish = self._finish(params)
        leaf = chain[-1]

        refs: dict[str, str | None] = {}
        ref_sources: dict[str, str] = {}
        offsets: dict[str, tuple[float, float, float]] = {}
        offset_sources: dict[str, str] = {}
        for v in chain:
            for slot_name, ref in v.slots.items():
                refs[slot_name] = ref
                ref_sources[slot_name] = v.id
            clean_offsets, offset_errors = validate_slot_offsets(v.slot_offsets, entity.slots)
            if offset_errors:
                raise RecipeError([f"{v.id}: {error}" for error in offset_errors])
            for slot_name, offset in clean_offsets.items():
                offsets[slot_name] = offset
                offset_sources[slot_name] = v.id

        slots, errors = self._resolve_slots(entity, refs, ref_sources, offsets, offset_sources)
        if errors:
            raise RecipeError(errors)

        source = self._manual_source("assets", entity_id, chain)
        # A manual composition is frozen in its .blend; slot budgets no longer describe it.
        composition = self._composition_for_asset(entity, chain) if source is None else None
        composition_report = (self._check_asset_composition(entity, composition, slots)
                              if composition is not None else None)

        slot_payload = self._slot_hash_payload(slots, finish)
        interface = entity.interface.model_dump(mode="json") if entity.interface else None
        hash_payload: dict[str, Any] = {"params": params, "level": leaf.level, "slots": slot_payload,
                                        "interface": interface}
        # Keep legacy zero-offset hashes, and therefore existing built GLBs, valid.
        # A nonzero placement adds a hash key so edited geometry receives its own artifact.
        if any(s.offset != (0.0, 0.0, 0.0) for s in slots.values()):
            hash_payload["slot_offsets"] = {name: s.offset for name, s in slots.items()}
        if entity.frontmatter.get("export_sockets"):
            hash_payload["export_sockets"] = True
        if composition is not None:
            composition_payload = composition.model_dump(mode="json")
            if composition.massing_grid is None:
                # Adding the optional field must not invalidate existing opt-in hashes.
                composition_payload.pop("massing_grid", None)
            hash_payload["composition"] = composition_payload
            # The composition check uses child envelopes and sockets. Keep its
            # report coupled to the build hash when those interfaces change.
            hash_payload["composition_interfaces"] = {
                name: slot.component.entity.interface.model_dump(mode="json")
                for name, slot in slots.items() if slot.component is not None
            }
        if source is not None:
            hash_payload["source"] = source.payload()
        if finish is not None:
            hash_payload["material_preset"] = finish
        self._asset_hash_payloads[(entity_id, vid)] = hash_payload
        digest = build_hash(f"assets/{entity_id}@{entity.generator_version}+b{BUILDER_VERSION}", hash_payload)
        return AssetResolution(entity, leaf, [v.id for v in chain], params, sources, sorted(leaf.params_delta),
                               slots, sorted(leaf.slots), sorted(leaf.slot_offsets), digest,
                               composition, composition_report, source, finish)

    @staticmethod
    def _finish_params(params: dict[str, Any], finish: dict[str, Any] | None) -> dict[str, Any]:
        """Keep resolved user parameters untouched when an assembly supplies its finish."""
        values = dict(params)
        if finish is not None and "material_preset" in values:
            values["material_preset"] = finish["preset"]
        return values

    def _slot_hash_payload(self, slots: dict[str, SlotResolution],
                           finish: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for name, slot in slots.items():
            child = slot.component
            if child is None:
                payload[name] = None
            elif isinstance(child, AssetResolution):
                payload[name] = {
                    "asset": child.entity.id,
                    "hash": self._overridden_asset_hash(child, finish) if finish is not None else child.hash,
                    "interface": child.entity.interface.model_dump(mode="json") if child.entity.interface else None,
                    "socket": slot.spec.socket,
                }
            else:
                # Opt-out assets retain the exact legacy component payload and hash.
                active = finish if finish is not None else child.finish
                payload[name] = {
                    "component": child.entity.id, "generator_version": child.entity.generator_version,
                    "params": self._finish_params(child.params, finish),
                    "level": child.variant.level, "socket": slot.spec.socket,
                }
                if child.source is not None:
                    payload[name]["source"] = child.source.payload()
                if active is not None:
                    payload[name]["material_preset"] = active
        return payload

    def _overridden_asset_hash(self, res: AssetResolution, finish: dict[str, Any]) -> str:
        """Hash a nested assembly's effective finish, excluding its superseded default."""
        payload = dict(self._asset_hash_payloads[(res.entity.id, res.variant.id)])
        payload["params"] = self._finish_params(res.params, finish)
        payload["slots"] = self._slot_hash_payload(res.slots, finish)
        payload["material_preset"] = finish
        return build_hash(f"assets/{res.entity.id}@{res.entity.generator_version}+b{BUILDER_VERSION}", payload)

    @staticmethod
    def _composition_for_asset(entity: EntityDoc, chain: list[AssetVariant]) -> CompositionIntent | None:
        """Resolve optional base intent plus variant deltas, just like asset parameters."""
        declared = entity.composition is not None
        values: dict[str, Any] = (entity.composition.model_dump(mode="json")
                                  if entity.composition is not None else {})
        for variant in chain:
            if variant.composition_delta:
                declared = True
                values = deep_merge(values, variant.composition_delta)
        if not declared:
            return None
        try:
            return CompositionIntent.model_validate(values)
        except ValidationError as exc:
            problems = [f"composition.{'.'.join(map(str, e['loc']))}: {e['msg']}"
                        for e in exc.errors()]
            raise RecipeError(problems) from exc

    @staticmethod
    def _check_asset_composition(entity: EntityDoc, intent: CompositionIntent,
                                 slots: dict[str, SlotResolution]) -> dict[str, Any]:
        """Check declared visual hierarchy against slot occupancy and interface envelopes.

        These budgets are independent of Blender and prior builds. Roof and front
        density use attachments directly mounted on the primary mass. Secondary
        decks have their own surfaces and are not counted against that mass twice.
        """
        errors: list[str] = []
        filled = {name: slot for name, slot in slots.items() if slot.component is not None}
        primary = intent.primary_mass
        hero = intent.hero_feature
        roles = [primary, hero, *intent.secondary_features]
        if len(set(roles)) != len(roles):
            errors.append("composition: primary_mass, hero_feature and secondary_features must be distinct")
        if primary not in filled:
            errors.append(f"composition.primary_mass '{primary}' must name an occupied slot")
        if not hero or hero not in filled:
            errors.append(f"composition.hero_feature '{hero}' must name one occupied slot")
        if len(intent.secondary_features) > 2:
            errors.append("composition.secondary_features: at most 2 occupied slots")
        for name in intent.secondary_features:
            if name not in filled:
                errors.append(f"composition.secondary_features '{name}' must name an occupied slot")
        for name in intent.slot_zones:
            if name not in slots:
                errors.append(f"composition.slot_zones: unknown slot '{name}'")
        if len(set(intent.quiet_zones)) != len(intent.quiet_zones):
            errors.append("composition.quiet_zones: duplicate quiet zone")

        for quiet in intent.quiet_zones:
            if quiet in slots:
                if quiet in filled:
                    errors.append(f"composition.quiet_zones: slot '{quiet}' is occupied")
                continue
            try:
                host, socket_name = split_socket_path(quiet, entity.body_slot() or "")
            except RecipeError:
                errors.append(f"composition.quiet_zones: invalid socket path '{quiet}'")
                continue
            host_slot = filled.get(host)
            host_interface = (host_slot.component.entity.interface
                              if host_slot and host_slot.component else None)
            if host_interface is None or host_interface.socket(socket_name) is None:
                errors.append(f"composition.quiet_zones: socket '{quiet}' is not available")
            elif any(slot.component is not None and slot.host == host and slot.socket == socket_name
                     for slot in slots.values()):
                errors.append(f"composition.quiet_zones: socket '{quiet}' is occupied")

        if errors:
            raise RecipeError(errors)
        assert filled[primary].component is not None
        mass_interface = filled[primary].component.entity.interface
        assert mass_interface is not None
        primary_grid = mass_interface.grid_size
        if min(primary_grid) <= 0:
            raise RecipeError("composition.primary_mass must have positive grid_size")
        massing_grid = intent.massing_grid or primary_grid
        if intent.massing_grid is not None:
            root_grid = entity.interface.grid_size if entity.interface else None
            if root_grid is None:
                raise RecipeError("composition.massing_grid requires an asset interface")
            if any(size < primary_size for size, primary_size in zip(massing_grid, primary_grid)):
                raise RecipeError(f"composition.massing_grid {list(massing_grid)} must contain "
                                  f"primary_mass grid {list(primary_grid)}")
            if any(size > root_size for size, root_size in zip(massing_grid, root_grid)):
                raise RecipeError(f"composition.massing_grid {list(massing_grid)} exceeds "
                                  f"asset grid {list(root_grid)}")
        mx, my, mz = massing_grid
        large_slots: list[str] = []
        roof_density = front_density = 0.0
        repeats: Counter[str] = Counter()
        for name, slot in filled.items():
            if name == primary:
                continue
            assert slot.component is not None
            attached = slot.component.entity
            interface = attached.interface
            assert interface is not None
            gx, gy, gz = interface.grid_size
            if name != entity.body_slot():
                # Wide but shallow parts still read as a large roof/facade attachment.
                footprint = max(gx * gz / (mx * mz), gx * gy / (mx * my),
                                gy * gz / (my * mz))
                if footprint >= 0.25:
                    large_slots.append(name)
                repeats[f"{attached.kind}/{attached.id}"] += 1

            if slot.host != primary:
                continue
            zone = intent.slot_zones.get(name)
            if zone is None and slot.socket:
                target = mass_interface.socket(slot.socket)
                if target and target.type == "roof":
                    zone = "roof"
                elif "front" in slot.socket or "facade" in slot.socket:
                    zone = "front"
            if zone == "roof":
                roof_density += gx * gz / (mx * mz)
            elif zone == "front":
                front_density += gx * gy / (mx * my)

        available = {(name, socket.name) for name, slot in filled.items()
                     for socket in (slot.component.entity.interface.sockets
                                    if slot.component and slot.component.entity.interface else [])}
        used = {(slot.host, slot.socket) for slot in filled.values()
                if slot.host is not None and slot.socket is not None}
        used &= available
        empty_ratio = ((len(available) - len(used)) / len(available)) if available else 1.0
        budget = intent.detail_budget
        if len(large_slots) > budget.max_large_attachments:
            errors.append(f"composition.detail_budget.max_large_attachments: {len(large_slots)} > "
                          f"{budget.max_large_attachments} ({', '.join(large_slots)})")
        for ref, count in sorted(repeats.items()):
            if count > budget.max_repeats_per_component:
                errors.append(f"composition.detail_budget.max_repeats_per_component: {ref} "
                              f"appears {count} times > {budget.max_repeats_per_component}")
        if roof_density > budget.max_roof_density + 1e-9:
            errors.append(f"composition.detail_budget.max_roof_density: {roof_density:.3f} > "
                          f"{budget.max_roof_density:.3f}")
        if front_density > budget.max_front_density + 1e-9:
            errors.append(f"composition.detail_budget.max_front_density: {front_density:.3f} > "
                          f"{budget.max_front_density:.3f}")
        if empty_ratio + 1e-9 < budget.min_empty_socket_ratio:
            errors.append(f"composition.detail_budget.min_empty_socket_ratio: {empty_ratio:.3f} < "
                          f"{budget.min_empty_socket_ratio:.3f}")
        if errors:
            raise RecipeError(errors)
        return {
            "status": "ok",
            "read_at_glance": intent.read_at_glance,
            "primary_mass": primary,
            "massing_grid": list(massing_grid),
            "massing_grid_source": "declared" if intent.massing_grid is not None else "primary_mass",
            "hero_feature": hero,
            "secondary_features": intent.secondary_features,
            "quiet_zones": intent.quiet_zones,
            "metrics": {
                "large_attachments": len(large_slots), "large_slots": large_slots,
                "repeats_per_component": dict(sorted(repeats.items())),
                "roof_density": round(roof_density, 4),
                "front_density": round(front_density, 4),
                "empty_socket_ratio": round(empty_ratio, 4),
                "available_sockets": len(available), "used_sockets": len(used),
            },
            "limits": budget.model_dump(mode="json"),
        }

    @staticmethod
    def slot_order(entity: EntityDoc) -> tuple[list[str], dict[str, tuple[str, str] | None], list[str]]:
        """Slots in dependency order (hosts before the slots mounted on them)."""
        errors: list[str] = []
        body = entity.body_slot()
        hosts: dict[str, tuple[str, str] | None] = {}
        for name, spec in entity.slots.items():
            if spec.socket is None:
                hosts[name] = None
                continue
            try:
                host, socket = split_socket_path(spec.socket, body or "")
            except RecipeError as exc:
                errors.extend(exc.errors)
                continue
            if host not in entity.slots:
                errors.append(f"slot '{name}': socket path '{spec.socket}' refers to unknown slot '{host}'")
                continue
            hosts[name] = (host, socket)
        order: list[str] = []
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in order or name not in hosts:
                return
            if name in visiting:
                errors.append(f"slot '{name}': mounting cycle")
                return
            visiting.add(name)
            link = hosts[name]
            if link is not None:
                visit(link[0])
            visiting.discard(name)
            order.append(name)

        for name in entity.slots:
            visit(name)
        return order, hosts, errors

    def _resolve_slots(self, entity: EntityDoc, refs: dict[str, str | None], ref_sources: dict[str, str],
                       offsets: dict[str, tuple[float, float, float]], offset_sources: dict[str, str]
                       ) -> tuple[dict[str, SlotResolution], list[str]]:
        body_name = entity.body_slot()
        if body_name is None:
            return {}, [f"assets/{entity.id}: no body slot (slot with socket: null)"]
        order, hosts, errors = self.slot_order(entity)
        for unknown in sorted(set(refs) - set(entity.slots)):
            errors.append(f"{ref_sources[unknown]}: unknown slot '{unknown}'")

        resolved: dict[str, SlotResolution] = {}
        for name in order:
            spec = entity.slots[name]
            link = hosts[name]
            ref = refs.get(name)
            slot = SlotResolution(name, spec, ref, ref_sources.get(name, "default"),
                                  host=link[0] if link else None, socket=link[1] if link else None,
                                  offset=offsets.get(name, (0.0, 0.0, 0.0)),
                                  offset_source=offset_sources.get(name, "default"))
            resolved[name] = slot
            if ref is None:
                if spec.required:
                    errors.append(f"slot '{name}' is required")
                continue
            host_doc: EntityDoc | None = None
            if link is not None:
                host_slot = resolved.get(link[0])
                if host_slot is None or host_slot.component is None:
                    errors.append(f"slot '{name}': host slot '{link[0]}' is empty or invalid")
                    continue
                host_doc = host_slot.component.entity
            try:
                ref_kind, comp_id, comp_vid = parse_entity_slot_ref(ref)
                comp = (self.resolve_asset(comp_id, comp_vid) if ref_kind == "assets"
                        else self.resolve_component(comp_id, comp_vid))
            except RecipeError as exc:
                errors.extend(f"slot '{name}': {e}" for e in exc.errors)
                continue
            reasons = slot_compatibility(name, spec, comp.entity, host_doc, slot.socket)
            if reasons:
                errors.extend(f"slot '{name}': {r}" for r in reasons)
                continue
            slot.component = comp
        return resolved, errors

    # ------------------------------------------------------------------ generic
    def resolve(self, kind: Kind, entity_id: str, vid: str) -> Resolution:
        if kind == "assets":
            return self.resolve_asset(entity_id, vid)
        return self.resolve_component(entity_id, vid, kind)

    def plan(self, kind: Kind, entity_id: str, vid: str) -> Plan:
        res = self.resolve(kind, entity_id, vid)
        entity = res.entity
        if kind == "materials":
            assert isinstance(res, ComponentResolution)
            return Plan(kind, entity_id, vid, res.hash, self._material_recipe(res), res)
        if entity.interface is None:
            raise RecipeError(f"{kind}/{entity_id}: interface is required to build")
        palette = self.store.palette()
        limits = self.cfg.limits
        if isinstance(res, ComponentResolution):
            parts = [{"slot": None, "host": None, "socket": None, "ref": res.ref,
                      "component": self._component_entry(res)}]
            poly_limit = limits.poly_limit_character if kind == "characters" else limits.poly_limit_component
        elif res.source is not None:
            # The whole composition is one hand-edited scene; slots are history, not geometry.
            parts = [{"slot": None, "host": None, "socket": None, "ref": f"assets/{entity_id}@{vid}",
                      "component": {"id": entity_id, "variant": vid, "generator_version": entity.generator_version,
                                    "params": {}, "level": res.variant.level,
                                    "interface": entity.interface.model_dump(mode="json"),
                                    "source_path": str(res.source.path)}}]
            poly_limit = limits.poly_limit_asset
        else:
            parts = self._asset_parts(res)
            poly_limit = limits.poly_limit_asset
        # A dense showcase or hero building may raise its own budget in _base.md.
        poly_limit = int(entity.frontmatter.get("poly_limit", poly_limit))
        recipe = {
            "kind": kind,
            "id": entity_id,
            "variant": vid,
            "hash": res.hash,
            "level": res.variant.level,
            "generator_version": entity.generator_version,
            "interface": entity.interface.model_dump(mode="json"),
            "palette": self._recipe_palette(palette.as_dict(), parts),
            "limits": {"polys": poly_limit, "bbox_tolerance": limits.bbox_tolerance},
            "preview": {"size": self.cfg.preview_size},
            "parts": parts,
        }
        if isinstance(res, ComponentResolution) and entity.design_intent is not None:
            recipe["design_intent"] = entity.design_intent.model_dump(mode="json")
        if kind == "characters":
            spec = entity.character or CharacterSpec()
            recipe["character"] = {"rig": spec.rig, "clips": spec.clips}
        if isinstance(res, AssetResolution) and res.source is not None:
            recipe["manual"] = True
        elif kind == "assets" and entity.frontmatter.get("export_sockets"):
            recipe["export_sockets"] = True
        if isinstance(res, AssetResolution) and res.composition_report is not None:
            recipe["composition"] = res.composition_report
        return Plan(kind, entity_id, vid, res.hash, recipe, res)

    def _asset_parts(self, res: AssetResolution,
                     finish: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        active = finish if finish is not None else res.finish
        parts: list[dict[str, Any]] = []
        for s in res.slots.values():
            if s.component is None:
                continue
            part: dict[str, Any] = {"slot": s.name, "host": s.host, "socket": s.socket,
                                    "ref": s.ref, "offset": s.offset}
            if isinstance(s.component, AssetResolution):
                part["asset"] = {
                    "id": s.component.entity.id, "variant": s.component.variant.id,
                    "hash": self._overridden_asset_hash(s.component, active) if active is not None else s.component.hash,
                    "interface": s.component.entity.interface.model_dump(mode="json"),
                    "export_sockets": bool(s.component.entity.frontmatter.get("export_sockets")),
                    "parts": self._asset_parts(s.component, active),
                }
            else:
                part["component"] = self._component_entry(s.component, active)
            parts.append(part)
        return parts

    def _recipe_palette(self, palette: dict[str, Any], parts: list[dict[str, Any]]) -> dict[str, Any]:
        """Apply finish classes to this recipe without changing the registry's palette."""
        finishes: dict[str, dict[str, Any]] = {}

        def collect(items: list[dict[str, Any]]) -> None:
            for part in items:
                if "asset" in part:
                    collect(part["asset"]["parts"])
                else:
                    finish = part["component"]["params"].get("_finish")
                    if finish is not None:
                        key = finish.get("texture_key", finish["preset"])
                        finishes[key] = self._finishes[key]

        collect(parts)
        if not finishes:
            return palette
        surfaces = dict(palette["surfaces"])
        types = dict(palette["surface_types"])
        assigned: dict[str, dict[str, float]] = {}
        for name, finish in finishes.items():
            for color, properties in finish["materials"].items():
                if color in assigned and assigned[color] != properties:
                    raise RecipeError(f"material presets in one asset disagree on PBR properties for '{color}'")
                assigned[color] = properties
                surface = f"finish_{name}_{color}"
                surfaces[color] = surface
                types[surface] = dict(properties)
        return {**palette, "surfaces": surfaces, "surface_types": types}

    def _material_recipe(self, res: ComponentResolution) -> dict[str, Any]:
        entity = res.entity
        path = self.store.generator_path(entity.id, "materials")
        if not path.is_file():
            raise RecipeError(f"materials/{entity.id}: blender.py not found")
        return {
            "kind": "materials",
            "id": entity.id,
            "variant": res.variant.id,
            "hash": res.hash,
            "level": res.variant.level,
            "generator_version": entity.generator_version,
            "shader": entity.shader,
            "params": res.params,
            "blender_path": str(path),
            "preview_models": [{"ref": m["ref"], "glb": m["glb"]} for m in res.models],
            "palette": self.store.palette().as_dict(),
            "preview": {"size": self.cfg.preview_size},
        }

    def _component_entry(self, res: ComponentResolution,
                          finish: dict[str, Any] | None = None) -> dict[str, Any]:
        assert res.entity.interface is not None
        active = finish if finish is not None else res.finish
        params = self._finish_params(res.params, finish)
        if active is not None:
            params["_finish"] = {"preset": active["preset"], "colors": dict(active["colors"])}
            if "texture_key" in active:
                params["_finish"]["texture_key"] = active["texture_key"]
        entry: dict[str, Any] = {
            "id": res.entity.id,
            "variant": res.variant.id,
            "generator_version": res.entity.generator_version,
            "params": params,
            "level": res.variant.level,
            "interface": res.entity.interface.model_dump(mode="json"),
        }
        if res.source is not None:
            entry["source_path"] = str(res.source.path)
            return entry
        path = self.store.generator_path(res.entity.id, res.entity.kind)
        if not path.is_file():
            raise RecipeError(f"{res.entity.kind}/{res.entity.id}: generator.py not found")
        entry["generator_path"] = str(path)
        return entry

    # ------------------------------------------------------------------ new variants
    def check_component_delta(self, entity_id: str, parent: str | None, delta: dict[str, Any],
                              kind: Kind = "components") -> dict[str, Any]:
        entity = self.entity(kind, entity_id)
        clean, errors = validate_params(entity.params, delta, partial=True)
        if parent is not None and parent not in self.variants(kind, entity_id):
            errors.append(f"parent '{parent}' not found")
        if errors:
            raise RecipeError(errors)
        return clean

    def check_asset_delta(self, entity_id: str, parent: str | None, slots: dict[str, str | None],
                          params_delta: dict[str, Any]) -> dict[str, Any]:
        entity = self.entity("assets", entity_id)
        clean, errors = validate_params(entity.params, params_delta, partial=True)
        if parent is not None and parent not in self.variants("assets", entity_id):
            errors.append(f"parent '{parent}' not found")
        errors.extend(f"unknown slot '{s}'" for s in slots if s not in entity.slots)
        if errors:
            raise RecipeError(errors)
        return clean

    def check_slot_offsets(self, entity_id: str, offsets: dict[str, tuple[float, float, float]]
                           ) -> dict[str, tuple[float, float, float]]:
        clean, errors = validate_slot_offsets(offsets, self.entity("assets", entity_id).slots)
        if errors:
            raise RecipeError(errors)
        return clean

    def slot_options(self, entity_id: str) -> dict[str, list[dict[str, Any]]]:
        """Built component and asset variants compatible with each slot's declared contract."""
        entity = self.entity("assets", entity_id)
        _order, hosts, _errors = self.slot_order(entity)
        docs: list[EntityDoc] = []
        for kind in ("components", "assets"):
            for candidate_id in self.store.entity_ids(kind):
                if kind == "assets" and candidate_id == entity_id:
                    continue
                try:
                    doc = self.entity(kind, candidate_id)
                except RecipeError:
                    continue
                if not doc.abstract and doc.interface is not None:
                    docs.append(doc)

        def compatible_docs(name: str, depth: int = 0) -> list[EntityDoc]:
            spec, link = entity.slots[name], hosts.get(name)
            if link is None or depth > 8:
                return [d for d in docs if not slot_compatibility(name, spec, d)]
            host_candidates = compatible_docs(link[0], depth + 1)
            return [d for d in docs
                    if any(not slot_compatibility(name, spec, d, h, link[1]) for h in host_candidates)]

        options: dict[str, list[dict[str, Any]]] = {}
        for name in entity.slots:
            items: list[dict[str, Any]] = []
            for doc in compatible_docs(name):
                for v in self.variants(doc.kind, doc.id).values():
                    if v.status not in ("built", "approved"):
                        continue
                    try:
                        digest = self.resolve(doc.kind, doc.id, v.id).hash
                    except RecipeError:
                        continue
                    ref = f"{doc.id}@{v.id}" if doc.kind == "components" else f"assets/{doc.id}@{v.id}"
                    items.append({"ref": ref, "kind": doc.kind,
                                  "component": doc.id if doc.kind == "components" else f"assets/{doc.id}",
                                  "variant": v.id, "status": v.status, "rating": v.rating,
                                  "note": v.note, "level": v.level, "type": doc.type, "hash": digest})
            options[name] = items
        return options
