"""Global catalog tags: edit metadata sources while preserving inherited recipes."""

from __future__ import annotations

import os
import re
import stat
import tempfile
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, SequenceNode

from .config import Config, RegistrySettings, render_priority_tags
from .index import Index
from .models import KINDS, Kind
from .planner import Planner
from .resolve import RecipeError
from .store import Store

TAG_KINDS: tuple[Kind, ...] = ("components", "assets")
EntityRef = tuple[Kind, str]
_FRONTMATTER = re.compile(r"\A(---[ \t]*\r?\n)(.*?)(\r?\n---[ \t]*(?:\r?\n|\Z))(.*)\Z", re.S)
_LOG = logging.getLogger(__name__)


def normalize_tag(name: str) -> str:
    name = name.strip()
    if not name or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise RecipeError("tag name must be non-empty and cannot contain control characters")
    return name


def _tags(data: dict[str, Any], path: Path) -> list[str]:
    tags = data.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise RecipeError(f"{path}: tags must be a list of strings")
    return tags


def _replace(tags: list[str], old: str, new: str | None) -> list[str]:
    return list(dict.fromkeys(new if tag == old else tag for tag in tags if tag != old or new is not None))


@dataclass
class _Document:
    path: Path
    original: bytes
    data: dict[str, Any]
    yaml_source: str
    prefix: str = ""
    suffix: str = ""

    @classmethod
    def read(cls, path: Path, *, markdown: bool = False) -> _Document:
        original = path.read_bytes()
        text = original.decode("utf-8")
        prefix = suffix = ""
        if markdown:
            match = _FRONTMATTER.match(text)
            if not match:
                raise RecipeError(f"{path}: expected YAML frontmatter")
            prefix, text, delimiter, prose = match.groups()
            suffix = delimiter + prose
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise RecipeError(f"{path}: {exc}") from exc
        if not isinstance(data, dict):
            raise RecipeError(f"{path}: expected a YAML mapping")
        _tags(data, path)
        return cls(path, original, data, text, prefix, suffix)

    def with_tags(self, tags: list[str]) -> bytes:
        expected = {**self.data, "tags": tags}
        source = self.yaml_source
        node = yaml.compose(source)
        pair = next(((key, value) for key, value in node.value if key.value == "tags"), None) \
            if isinstance(node, MappingNode) else None
        flow = yaml.safe_dump(tags, allow_unicode=True, default_flow_style=True, width=100000).strip()
        newline = "\r\n" if "\r\n" in source else "\n"
        if pair is None:
            candidate = source.rstrip("\r\n") + newline + f"tags: {flow}"
        else:
            key, value = pair
            if isinstance(value, SequenceNode) and value.flow_style:
                candidate = source[:value.start_mark.index] + flow + source[value.end_mark.index:]
            else:
                # Block-list end marks can include comments preceding the next field.
                # Keep those comments, and keep an inline explanation on `tags:`.
                old_block = source[key.start_mark.index:value.end_mark.index]
                header = old_block.splitlines()[0] if old_block else ""
                comment = re.search(r":\s*(#.*)$", header)
                comments = [line for line in old_block.splitlines()[1:] if line.lstrip().startswith("#")]
                replacement = f"tags: {flow}" + (f"  {comment.group(1)}" if comment else "") + newline
                if comments:
                    replacement += newline.join(comments) + newline
                candidate = source[:key.start_mark.index] + replacement + source[value.end_mark.index:]
        # Aliases may point to marks outside `tags`; never let a textual edit alter a recipe.
        try:
            valid = yaml.safe_load(candidate) == expected
        except yaml.YAMLError:
            valid = False
        if not valid:
            candidate = yaml.safe_dump(expected, allow_unicode=True, sort_keys=False)
        if yaml.safe_load(candidate) != expected:
            raise RecipeError(f"{self.path}: could not safely update tags")
        return (self.prefix + candidate + self.suffix).encode("utf-8")


@dataclass
class _Snapshot:
    entities: dict[EntityRef, _Document]
    variants: dict[tuple[Kind, str, str], _Document]
    effective: dict[EntityRef, tuple[list[str], EntityRef | None, list[EntityRef]]]


class TagCatalog:
    def __init__(self, cfg: Config, store: Store, index: Index):
        self.cfg, self.store, self.index = cfg, store, index

    def _snapshot(self) -> _Snapshot:
        entities: dict[EntityRef, _Document] = {}
        variants: dict[tuple[Kind, str, str], _Document] = {}
        for kind in TAG_KINDS:
            for eid in self.store.entity_ids(kind):
                folder = self.store.entity_dir(kind, eid)
                entities[kind, eid] = _Document.read(folder / "_base.md", markdown=True)
                for path in sorted((folder / "variants").glob("*.yaml")):
                    variants[kind, eid, path.stem] = _Document.read(path)

        documents = dict(entities)
        effective = {}
        for ref in entities:
            kind, eid = ref
            chain: list[EntityRef] = []
            current: str | None = eid
            while current:
                owner = next(((k, current) for k in (kind, *(k for k in KINDS if k != kind))
                              if self.store.has_entity(k, current)), None)
                if owner is None:
                    raise RecipeError(f"{kind}/{eid}: parent '{current}' not found")
                if owner in chain:
                    raise RecipeError(f"{kind}/{eid}: inheritance cycle")
                chain.append(owner)
                if owner not in documents:
                    documents[owner] = _Document.read(self.store.entity_dir(*owner) / "_base.md", markdown=True)
                doc = documents[owner]
                if "tags" in doc.data:
                    effective[ref] = (_tags(doc.data, doc.path), owner, chain)
                    break
                current = doc.data.get("inherits")
                if current is not None and not isinstance(current, str):
                    raise RecipeError(f"{doc.path}: inherits must be an entity id")
            else:
                effective[ref] = ([], None, chain)
        return _Snapshot(entities, variants, effective)

    def _inventory(self, snapshot: _Snapshot) -> list[dict[str, Any]]:
        refs: dict[str, set[EntityRef]] = {tag: set() for tag in self.cfg.priority_tags}
        counts: dict[str, int] = {}
        for ref, (tags, _owner, _chain) in snapshot.effective.items():
            for tag in set(tags):
                refs.setdefault(tag, set()).add(ref)
        for (kind, eid, _vid), doc in snapshot.variants.items():
            for tag in set(_tags(doc.data, doc.path)):
                refs.setdefault(tag, set()).add((kind, eid))
                counts[tag] = counts.get(tag, 0) + 1
        return [{"name": name, "entity_count": len(entities), "variant_count": counts.get(name, 0),
                 "entities": [{"kind": kind, "id": eid} for kind, eid in sorted(entities)]}
                for name, entities in sorted(refs.items(), key=lambda item: (item[0].casefold(), item[0]))]

    def inventory(self) -> dict[str, Any]:
        with self.store.write_lock:
            return {"tags": self._inventory(self._snapshot())}

    def change(self, old: str, new: str | None, *,
               notify: Callable[[list[EntityRef]], None] | None = None) -> dict[str, Any]:
        if new is not None:
            new = normalize_tag(new)
        with self.store.write_lock:
            snapshot = self._snapshot()
            item = next((tag for tag in self._inventory(snapshot) if tag["name"] == old), None)
            if item is None:
                raise FileNotFoundError(f"tag '{old}'")
            if new == old:
                return {"old_name": old, "name": new, "changed_entities": 0, "changed_variants": 0}
            changes: dict[Path, tuple[bytes | None, bytes]] = {}
            for doc in snapshot.entities.values():
                tags = _tags(doc.data, doc.path)
                if old in tags:
                    changes[doc.path] = (doc.original, doc.with_tags(_replace(tags, old, new)))
            # Keep external materials/characters untouched. A scoped ancestor can override
            # their inherited tag list for its own components/assets descendants.
            for _ref, (tags, owner, chain) in snapshot.effective.items():
                if old in tags and owner not in snapshot.entities:
                    boundary = next(ref for ref in reversed(chain) if ref in snapshot.entities)
                    doc = snapshot.entities[boundary]
                    changes[doc.path] = (doc.original, doc.with_tags(_replace(tags, old, new)))
            changed_variants = 0
            for doc in snapshot.variants.values():
                tags = _tags(doc.data, doc.path)
                if old in tags:
                    changes[doc.path] = (doc.original, doc.with_tags(_replace(tags, old, new)))
                    changed_variants += 1
            priority_tags = _replace(self.cfg.priority_tags, old, new)
            priority_tags = RegistrySettings(priority_tags=priority_tags).priority_tags
            if priority_tags != self.cfg.priority_tags:
                path = self.cfg._source_path
                original = path.read_bytes() if path.exists() else None
                source = (original or b"").decode("utf-8")
                changes[path] = (original, render_priority_tags(source, priority_tags).encode("utf-8"))
            self._commit(changes)
            self.cfg.priority_tags = priority_tags
            if notify is not None:
                try:
                    notify([(ref["kind"], ref["id"]) for ref in item["entities"]])
                except Exception:
                    _LOG.exception("could not publish committed tag update")
            return {"old_name": old, "name": new, "changed_entities": item["entity_count"],
                    "changed_variants": changed_variants}

    @staticmethod
    def _stage(path: Path, content: bytes, mode: int | None) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        staged: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.tags-", delete=False) as tmp:
                staged = Path(tmp.name)
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
            if mode is not None:
                staged.chmod(mode)
            return staged
        except BaseException:
            if staged is not None:
                staged.unlink(missing_ok=True)
            raise

    def _commit(self, changes: dict[Path, tuple[bytes | None, bytes]]) -> None:
        staged: dict[Path, tuple[Path, Path | None]] = {}
        applied: list[Path] = []
        keep_backups: set[Path] = set()
        try:
            for path, (original, content) in changes.items():
                current = path.read_bytes() if path.exists() else None
                if current != original:
                    raise RecipeError(f"{path}: changed while preparing tag update; retry")
                mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
                replacement = self._stage(path, content, mode)
                staged[path] = (replacement, None)
                backup = self._stage(path, original, mode) if original is not None else None
                staged[path] = (replacement, backup)
            # Editors and CLI processes do not share this Store's in-process lock.
            # Detect changes made while preparing the full batch before replacing any file.
            for path, (original, _content) in changes.items():
                current = path.read_bytes() if path.exists() else None
                if current != original:
                    raise RecipeError(f"{path}: changed while preparing tag update; retry")
            for path, (replacement, _backup) in staged.items():
                os.replace(replacement, path)
                applied.append(path)
            # Reindex commits all rows together. A failure leaves the old index transaction intact.
            self.index.reindex(Planner(self.store, self.cfg), self.cfg.build_dir)
        except BaseException as exc:
            rollback_errors: list[str] = []
            for path in reversed(applied):
                backup = staged[path][1]
                try:
                    if backup is None:
                        path.unlink(missing_ok=True)
                    else:
                        os.replace(backup, path)
                except OSError as rollback_exc:
                    if backup is not None:
                        keep_backups.add(backup)
                    rollback_errors.append(f"{path}: {rollback_exc}; backup: {backup}")
            if rollback_errors:
                raise RuntimeError("tag update rollback failed: " + "; ".join(rollback_errors)) from exc
            raise
        finally:
            for replacement, backup in staged.values():
                replacement.unlink(missing_ok=True)
                if backup is not None and backup not in keep_backups:
                    backup.unlink(missing_ok=True)
