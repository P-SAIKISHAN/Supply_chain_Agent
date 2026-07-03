from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONB_TYPE, TimestampMixin


class IntelligenceChunk(TimestampMixin, Base):
    """Chunked segment of an intelligence document used for retrieval."""

    __tablename__ = "intelligence_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("intelligence_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSONB_TYPE, nullable=False, default=dict)

    document = relationship("IntelligenceDocument", back_populates="chunks")

