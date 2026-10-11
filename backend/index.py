"""SQLite index over the registry files. Disposable: `reindex` rebuilds it from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .models import KINDS, Kind, Variant
from .planner import Planner
from .resolve import RecipeError


class EntityRow(SQLModel, table=True):
    key: str = Field(primary_key=True)
    kind: str = Field(index=True)
    entity_id: str
    title: str = ""
    type: str = "part"
    category: str | None = None
    inherits: str | None = None
    abstract: bool = False
    complexity_level: int = 0
    tags: str = "[]"
    error: str | None = None


class VariantRow(SQLModel, table=True):
    key: str = Field(primary_key=True)
    kind: str = Field(index=True)
    entity_id: str = Field(index=True)
    vid: str
    parent: str | None = None
    level: int = 1
    status: str = "draft"
    rating: int | None = None
    tags: str = "[]"
    note: str = ""
    author: str = "human"
    created: str | None = None
    hash: str | None = Field(default=None, index=True)
    error: str | None = None


class BuildRow(SQLModel, table=True):
    hash: str = Field(primary_key=True)
    state: str  # ok | failed
    kind: str | None = None
    entity_id: str | None = None
    vid: str | None = None
    built_at: str | None = None
    duration_s: float | None = None
    message: str | None = None


def entity_key(kind: str, entity_id: str) -> str:
    return f"{kind}/{entity_id}"


def variant_key(kind: str, entity_id: str, vid: str) -> str:
    return f"{kind}/{entity_id}/{vid}"


SCHEMA_VERSION = 2  # bump when table columns change; the index is rebuilt from files anyway


class Index:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            version = conn.exec_driver_sql("PRAGMA user_version").scalar()
        if version != SCHEMA_VERSION:
            SQLModel.metadata.drop_all(self.engine)
            with self.engine.begin() as conn:
                conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
        SQLModel.metadata.create_all(self.engine)

    def session(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    # ------------------------------------------------------------------ rebuild
    def reindex(self, planner: Planner, build_dir: Path) -> dict[str, int]:
        store = planner.store
        entities: list[EntityRow] = []
        variants: list[VariantRow] = []
        for kind in KINDS:
            for eid in store.entity_ids(kind):
                row = EntityRow(key=entity_key(kind, eid), kind=kind, entity_id=eid)
                try:
                    doc = planner.entity(kind, eid)
                    row.title = doc.title or eid
                    row.type = doc.type
                    row.category = doc.category
                    row.inherits = doc.inherits
                    row.abstract = doc.abstract
                    row.complexity_level = doc.complexity_level
                    row.tags = json.dumps(doc.tags, ensure_ascii=False)
                except RecipeError as exc:
                    row.error = str(exc)
                entities.append(row)
                if row.error or row.abstract:
                    continue
                for variant in store.variants(kind, eid)[0].values():
                    variants.append(self._variant_row(planner, kind, eid, variant))

        builds = [row for path in sorted(build_dir.glob("*/report.json")) if (row := build_row_from_report(path))]
        with self.session() as s:
            for model in (EntityRow, VariantRow, BuildRow):
                s.exec(delete(model))  # type: ignore[call-overload]
            s.add_all([*entities, *variants, *builds])
            s.commit()
        return {"entities": len(entities), "variants": len(variants), "builds": len(builds)}

    @staticmethod
    def _variant_row(planner: Planner, kind: Kind, entity_id: str, variant: Variant) -> VariantRow:
        row = VariantRow(
            key=variant_key(kind, entity_id, variant.id), kind=kind, entity_id=entity_id, vid=variant.id,
            parent=variant.parent, level=variant.level, status=variant.status, rating=variant.rating,
            tags=json.dumps(variant.tags, ensure_ascii=False), note=variant.note, author=variant.author,
            created=variant.created,
        )
        try:
            row.hash = planner.resolve(kind, entity_id, variant.id).hash
        except RecipeError as exc:
            row.error = str(exc)
        return row

    # ------------------------------------------------------------------ writes
    def upsert_variant(self, planner: Planner, kind: Kind, entity_id: str, variant: Variant) -> VariantRow:
        row = self._variant_row(planner, kind, entity_id, variant)
        with self.session() as s:
            s.merge(row)
            s.commit()
        return row

    def record_build(self, report_path: Path) -> BuildRow | None:
        row = build_row_from_report(report_path)
        if row is not None:
            with self.session() as s:
                s.merge(row)
                s.commit()
        return row

    # ------------------------------------------------------------------ reads
    def entities(self, kind: Kind) -> list[EntityRow]:
        with self.session() as s:
            return list(s.exec(select(EntityRow).where(EntityRow.kind == kind).order_by(EntityRow.entity_id)))

    def variants(self, kind: Kind, entity_id: str | None = None) -> list[VariantRow]:
        with self.session() as s:
            query = select(VariantRow).where(VariantRow.kind == kind)
            if entity_id is not None:
                query = query.where(VariantRow.entity_id == entity_id)
            return list(s.exec(query.order_by(VariantRow.entity_id, VariantRow.vid)))

    def all_variants(self) -> list[VariantRow]:
        with self.session() as s:
            return list(s.exec(select(VariantRow).order_by(VariantRow.key)))

    def variant(self, kind: Kind, entity_id: str, vid: str) -> VariantRow | None:
        with self.session() as s:
            return s.get(VariantRow, variant_key(kind, entity_id, vid))

    def builds(self, hashes: list[str]) -> dict[str, BuildRow]:
        if not hashes:
            return {}
        with self.session() as s:
            rows = s.exec(select(BuildRow).where(BuildRow.hash.in_(hashes)))  # type: ignore[attr-defined]
            return {r.hash: r for r in rows}


def build_row_from_report(path: Path) -> BuildRow | None:
    try:
        report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict):
        return None
    return BuildRow(
        hash=path.parent.name,
        state="ok" if report.get("status") == "ok" else "failed",
        kind=report.get("kind"),
        entity_id=report.get("id"),
        vid=report.get("variant"),
        built_at=report.get("built_at"),
        duration_s=report.get("duration_s"),
        message=report.get("error"),
    )
