from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Shipment(TimestampMixin, Base):
    """Active or historical shipment record used for logistics monitoring."""

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    supplier_country_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_countries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_port_id: Mapped[int] = mapped_column(
        ForeignKey("ports.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    destination_port_id: Mapped[int] = mapped_column(
        ForeignKey("ports.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    corridor_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_corridors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tanker_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cargo_volume_bbl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    crude_grade: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    freight_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    supplier_country = relationship("SupplierCountry", back_populates="shipments")
    source_port = relationship(
        "Port",
        foreign_keys=[source_port_id],
        back_populates="source_shipments",
    )
    destination_port = relationship(
        "Port",
        foreign_keys=[destination_port_id],
        back_populates="destination_shipments",
    )
    corridor = relationship("ShippingCorridor", back_populates="shipments")

