from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class CommodityPrice(TimestampMixin, Base):
    """Commodity benchmark price observation."""

    __tablename__ = "commodity_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    benchmark_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(220), nullable=False, index=True)

