from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def upsert_row(db: Session, model: type[Any], lookup: dict[str, Any], values: dict[str, Any]) -> tuple[Any, bool]:
    """Create or update a row using a stable natural key lookup.

    Returns the ORM object and a boolean flag indicating whether the row was created.
    """
    instance = db.query(model).filter_by(**lookup).one_or_none()
    if instance is None:
        payload = {**lookup, **values}
        instance = model(**payload)
        db.add(instance)
        db.flush()
        return instance, True

    for field, value in values.items():
        setattr(instance, field, value)
    db.flush()
    return instance, False


class BaseIngestor(ABC):
    """Common ingestion lifecycle: fetch -> normalize -> persist."""

    source_name: str = "unknown"
    demo_mode: bool = True

    def __init__(self, demo_mode: bool = True) -> None:
        self.demo_mode = demo_mode
        self.logger = logging.getLogger(f"app.ingestion.{self.source_name}")

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw records from a source or demo generator."""

    @abstractmethod
    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw records into canonical platform payloads."""

    @abstractmethod
    def persist(self, db: Session, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Write normalized records into the database."""

    def run(self, db: Session) -> dict[str, Any]:
        """Execute a full ingestion pass and return a run summary."""
        started_at = utcnow()
        raw_records = self.fetch()
        normalized_records = self.normalize(raw_records)
        persist_summary = self.persist(db, normalized_records)
        finished_at = utcnow()
        return {
            "source": self.source_name,
            "demo_mode": self.demo_mode,
            "started_at": started_at,
            "finished_at": finished_at,
            "fetched_count": len(raw_records),
            "normalized_count": len(normalized_records),
            **persist_summary,
        }

