from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import JSONB_TYPE, TimestampMixin


class GeopoliticalEvent(TimestampMixin, Base):
    """Geopolitical or security event that can influence energy supply risk."""

    __tablename__ = "geopolitical_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    extracted_entities: Mapped[dict] = mapped_column(JSONB_TYPE, nullable=False, default=dict)
    impact_tags: Mapped[list[str]] = mapped_column(JSONB_TYPE, nullable=False, default=list)

