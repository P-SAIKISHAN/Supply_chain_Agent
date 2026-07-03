from datetime import date

from sqlalchemy import Date, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class SanctionsEvent(TimestampMixin, Base):
    """Sanctions-related event affecting supply access or trade flows."""

    __tablename__ = "sanctions_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_entity: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    sanction_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

