from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONB_TYPE, TimestampMixin


class SupplierCountry(TimestampMixin, Base):
    """Country-level supplier profile with baseline risk factors."""

    __tablename__ = "supplier_countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    crude_grade_types: Mapped[list[str]] = mapped_column(JSONB_TYPE, nullable=False, default=list)
    geopolitical_risk_base: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sanctions_risk_base: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    shipments = relationship("Shipment", back_populates="supplier_country")

