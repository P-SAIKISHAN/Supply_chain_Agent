from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONB_TYPE, TimestampMixin


class IntelligenceDocument(TimestampMixin, Base):
    """Stored intelligence note, source document, or knowledge artifact."""

    __tablename__ = "intelligence_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB_TYPE, nullable=False, default=dict)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    chunks = relationship(
        "IntelligenceChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

