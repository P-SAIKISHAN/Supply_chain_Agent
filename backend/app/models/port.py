from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Port(TimestampMixin, Base):
    """Port or terminal used as shipment source, transit, or destination."""

    __tablename__ = "ports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    port_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    congestion_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    linked_refineries = relationship("Refinery", back_populates="linked_port")
    source_shipments = relationship(
        "Shipment",
        foreign_keys="Shipment.source_port_id",
        back_populates="source_port",
    )
    destination_shipments = relationship(
        "Shipment",
        foreign_keys="Shipment.destination_port_id",
        back_populates="destination_port",
    )

