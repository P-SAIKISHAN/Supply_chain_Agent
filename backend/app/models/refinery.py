from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONB_TYPE, TimestampMixin


class Refinery(TimestampMixin, Base):
    """Refinery profile with crude compatibility and strategic importance data."""

    __tablename__ = "refineries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    capacity_bpd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    complexity_index: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    compatible_crude_grades: Mapped[list[str]] = mapped_column(JSONB_TYPE, nullable=False, default=list)
    linked_port_id: Mapped[int | None] = mapped_column(
        ForeignKey("ports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    strategic_priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    linked_port = relationship("Port", back_populates="linked_refineries")
    recommendations = relationship("ProcurementRecommendation", back_populates="refinery")

