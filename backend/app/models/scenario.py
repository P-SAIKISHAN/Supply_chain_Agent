from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONB_TYPE, TimestampMixin


class Scenario(TimestampMixin, Base):
    """Simulation scenario created by users to test supply chain disruption cases."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    scenario_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    trigger_description: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSONB_TYPE, nullable=False, default=dict)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    creator = relationship("User", back_populates="scenarios")
    scenario_result = relationship(
        "ScenarioResult",
        back_populates="scenario",
        uselist=False,
        cascade="all, delete-orphan",
    )
    recommendations = relationship("ProcurementRecommendation", back_populates="scenario")
    spr_plan = relationship("SPRPlan", back_populates="scenario", uselist=False)


class ScenarioResult(TimestampMixin, Base):
    """Computed results and impact estimates for a scenario run."""

    __tablename__ = "scenario_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    estimated_supply_loss_pct: Mapped[float] = mapped_column(default=0.0)
    refinery_utilization_impact: Mapped[float] = mapped_column(default=0.0)
    fuel_price_impact_pct: Mapped[float] = mapped_column(default=0.0)
    logistics_cost_impact_pct: Mapped[float] = mapped_column(default=0.0)
    gdp_impact_estimate: Mapped[float] = mapped_column(default=0.0)
    output_json: Mapped[dict] = mapped_column(JSONB_TYPE, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    scenario = relationship("Scenario", back_populates="scenario_result")
