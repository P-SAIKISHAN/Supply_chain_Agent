from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models import (
    CommodityPrice,
    GeopoliticalEvent,
    Port,
    ProcurementRecommendation,
    Refinery,
    RiskScore,
    SanctionsEvent,
    Scenario,
    ScenarioResult,
    Shipment,
    ShippingCorridor,
    SPRPlan,
    SupplierCountry,
    User,
)
from app.schemas.reports import KnowledgeDocumentCreateRequest
from app.services.rag_service import ingest_intelligence_document

UTC = timezone.utc


def upsert_by_lookup(
    db: Session,
    model: type[Any],
    lookup: dict[str, Any],
    values: dict[str, Any],
) -> Any:
    """Create or update a row using a stable natural key lookup."""
    instance = db.query(model).filter_by(**lookup).one_or_none()
    if instance is None:
        payload = {**lookup, **values}
        instance = model(**payload)
        db.add(instance)
        db.flush()
        return instance

    for field, value in values.items():
        setattr(instance, field, value)
    db.flush()
    return instance


def seed_users(db: Session) -> dict[str, User]:
    """Seed demo users for immediate login in local environments."""
    users = {
        "admin": upsert_by_lookup(
            db,
            User,
            {"email": "demo.admin@energy.local"},
            {
                "full_name": "Demo Admin",
                "hashed_password": get_password_hash("DemoAdmin123!"),
                "role": "admin",
                "is_active": True,
            },
        ),
        "analyst": upsert_by_lookup(
            db,
            User,
            {"email": "demo.analyst@energy.local"},
            {
                "full_name": "Demo Analyst",
                "hashed_password": get_password_hash("DemoAnalyst123!"),
                "role": "analyst",
                "is_active": True,
            },
        ),
    }
    return users


def seed_supplier_countries(db: Session) -> dict[str, SupplierCountry]:
    countries = [
        {
            "name": "Saudi Arabia",
            "region": "Middle East",
            "crude_grade_types": ["Arab Light", "Arab Medium", "Arab Heavy"],
            "geopolitical_risk_base": 0.46,
            "sanctions_risk_base": 0.18,
            "reliability_score": 0.91,
            "active": True,
        },
        {
            "name": "Iraq",
            "region": "Middle East",
            "crude_grade_types": ["Basrah Light", "Basrah Heavy"],
            "geopolitical_risk_base": 0.62,
            "sanctions_risk_base": 0.24,
            "reliability_score": 0.79,
            "active": True,
        },
        {
            "name": "UAE",
            "region": "Middle East",
            "crude_grade_types": ["Upper Zakum", "Das", "Murban"],
            "geopolitical_risk_base": 0.34,
            "sanctions_risk_base": 0.12,
            "reliability_score": 0.95,
            "active": True,
        },
        {
            "name": "Russia",
            "region": "Eurasia",
            "crude_grade_types": ["Urals", "ESPO"],
            "geopolitical_risk_base": 0.81,
            "sanctions_risk_base": 0.88,
            "reliability_score": 0.52,
            "active": True,
        },
        {
            "name": "USA",
            "region": "North America",
            "crude_grade_types": ["WTI", "Mars", "LLS"],
            "geopolitical_risk_base": 0.22,
            "sanctions_risk_base": 0.08,
            "reliability_score": 0.97,
            "active": True,
        },
        {
            "name": "Nigeria",
            "region": "Africa",
            "crude_grade_types": ["Bonny Light", "Qua Iboe"],
            "geopolitical_risk_base": 0.55,
            "sanctions_risk_base": 0.15,
            "reliability_score": 0.77,
            "active": True,
        },
    ]

    seeded: dict[str, SupplierCountry] = {}
    for item in countries:
        seeded[item["name"]] = upsert_by_lookup(db, SupplierCountry, {"name": item["name"]}, item)
    return seeded


def seed_corridors(db: Session) -> dict[str, ShippingCorridor]:
    corridors = [
        {
            "name": "Strait of Hormuz",
            "corridor_type": "maritime chokepoint",
            "risk_level": "high",
            "status": "open",
            "typical_transit_days": 7,
            "notes": "Critical route for Gulf crude flows to Asia.",
        },
        {
            "name": "Red Sea",
            "corridor_type": "maritime corridor",
            "risk_level": "high",
            "status": "degraded",
            "typical_transit_days": 10,
            "notes": "Subject to disruption from regional conflict and attacks.",
        },
        {
            "name": "Cape of Good Hope",
            "corridor_type": "diversion route",
            "risk_level": "medium",
            "status": "open",
            "typical_transit_days": 18,
            "notes": "Longer alternate route when Red Sea is compromised.",
        },
    ]

    seeded: dict[str, ShippingCorridor] = {}
    for item in corridors:
        seeded[item["name"]] = upsert_by_lookup(db, ShippingCorridor, {"name": item["name"]}, item)
    return seeded


def seed_ports(db: Session) -> dict[str, Port]:
    ports = [
        {
            "name": "Jamnagar",
            "country": "India",
            "latitude": 22.4707,
            "longitude": 70.0577,
            "port_type": "refinery port",
            "congestion_score": 0.35,
            "active": True,
        },
        {
            "name": "Vadinar",
            "country": "India",
            "latitude": 22.4655,
            "longitude": 69.7512,
            "port_type": "oil terminal",
            "congestion_score": 0.28,
            "active": True,
        },
        {
            "name": "Paradip",
            "country": "India",
            "latitude": 20.3164,
            "longitude": 86.6186,
            "port_type": "major port",
            "congestion_score": 0.41,
            "active": True,
        },
        {
            "name": "Mangalore",
            "country": "India",
            "latitude": 12.9141,
            "longitude": 74.8553,
            "port_type": "major port",
            "congestion_score": 0.22,
            "active": True,
        },
        {
            "name": "Mumbai",
            "country": "India",
            "latitude": 18.9319,
            "longitude": 72.8208,
            "port_type": "major port",
            "congestion_score": 0.44,
            "active": True,
        },
        {
            "name": "Ras Tanura",
            "country": "Saudi Arabia",
            "latitude": 26.6431,
            "longitude": 50.1608,
            "port_type": "export terminal",
            "congestion_score": 0.19,
            "active": True,
        },
        {
            "name": "Basra Oil Terminal",
            "country": "Iraq",
            "latitude": 29.6990,
            "longitude": 48.6839,
            "port_type": "export terminal",
            "congestion_score": 0.33,
            "active": True,
        },
        {
            "name": "Fujairah",
            "country": "UAE",
            "latitude": 25.1288,
            "longitude": 56.3265,
            "port_type": "bunkering hub",
            "congestion_score": 0.27,
            "active": True,
        },
        {
            "name": "Bonny Terminal",
            "country": "Nigeria",
            "latitude": 4.4500,
            "longitude": 7.1700,
            "port_type": "export terminal",
            "congestion_score": 0.31,
            "active": True,
        },
    ]

    seeded: dict[str, Port] = {}
    for item in ports:
        seeded[item["name"]] = upsert_by_lookup(db, Port, {"name": item["name"]}, item)
    return seeded


def seed_refineries(db: Session, ports: dict[str, Port]) -> dict[str, Refinery]:
    refineries = [
        {
            "name": "Jamnagar Refinery",
            "company": "Reliance Industries",
            "state": "Gujarat",
            "capacity_bpd": 1240000,
            "complexity_index": 14.2,
            "compatible_crude_grades": ["Arab Light", "Arab Medium", "Basrah Light", "Bonny Light"],
            "linked_port_id": ports["Vadinar"].id,
            "strategic_priority_score": 0.98,
        },
        {
            "name": "Paradip Refinery",
            "company": "Indian Oil Corporation",
            "state": "Odisha",
            "capacity_bpd": 300000,
            "complexity_index": 11.8,
            "compatible_crude_grades": ["Arab Light", "Basrah Light", "WTI"],
            "linked_port_id": ports["Paradip"].id,
            "strategic_priority_score": 0.87,
        },
        {
            "name": "Panipat Refinery",
            "company": "Indian Oil Corporation",
            "state": "Haryana",
            "capacity_bpd": 300000,
            "complexity_index": 12.1,
            "compatible_crude_grades": ["Arab Light", "Basrah Heavy", "Urals"],
            "linked_port_id": None,
            "strategic_priority_score": 0.81,
        },
        {
            "name": "Kochi Refinery",
            "company": "BPCL",
            "state": "Kerala",
            "capacity_bpd": 310000,
            "complexity_index": 10.9,
            "compatible_crude_grades": ["Arab Light", "Murban", "WTI"],
            "linked_port_id": ports["Mangalore"].id,
            "strategic_priority_score": 0.74,
        },
        {
            "name": "Numaligarh Refinery",
            "company": "Numaligarh Refinery Limited",
            "state": "Assam",
            "capacity_bpd": 60000,
            "complexity_index": 9.4,
            "compatible_crude_grades": ["WTI", "Light Sweet"],
            "linked_port_id": None,
            "strategic_priority_score": 0.61,
        },
    ]

    seeded: dict[str, Refinery] = {}
    for item in refineries:
        seeded[item["name"]] = upsert_by_lookup(db, Refinery, {"name": item["name"]}, item)
    return seeded


def seed_shipments(
    db: Session,
    countries: dict[str, SupplierCountry],
    corridors: dict[str, ShippingCorridor],
    ports: dict[str, Port],
) -> list[Shipment]:
    shipment_rows = [
        {
            "tanker_name": "MT Horizon Star",
            "supplier_country_id": countries["Saudi Arabia"].id,
            "source_port_id": ports["Ras Tanura"].id,
            "destination_port_id": ports["Vadinar"].id,
            "corridor_id": corridors["Strait of Hormuz"].id,
            "cargo_volume_bbl": 2000000,
            "crude_grade": "Arab Light",
            "eta": datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
            "status": "in_transit",
            "freight_cost": 8400000,
            "risk_flag": False,
        },
        {
            "tanker_name": "MT Basrah Pearl",
            "supplier_country_id": countries["Iraq"].id,
            "source_port_id": ports["Basra Oil Terminal"].id,
            "destination_port_id": ports["Paradip"].id,
            "corridor_id": corridors["Strait of Hormuz"].id,
            "cargo_volume_bbl": 1800000,
            "crude_grade": "Basrah Light",
            "eta": datetime(2026, 7, 15, 15, 0, tzinfo=UTC),
            "status": "planned",
            "freight_cost": 7600000,
            "risk_flag": True,
        },
        {
            "tanker_name": "MT Desh Navigator",
            "supplier_country_id": countries["UAE"].id,
            "source_port_id": ports["Fujairah"].id,
            "destination_port_id": ports["Mumbai"].id,
            "corridor_id": corridors["Red Sea"].id,
            "cargo_volume_bbl": 1600000,
            "crude_grade": "Murban",
            "eta": datetime(2026, 7, 18, 8, 0, tzinfo=UTC),
            "status": "scheduled",
            "freight_cost": 6900000,
            "risk_flag": False,
        },
        {
            "tanker_name": "MT Atlantic Pride",
            "supplier_country_id": countries["Nigeria"].id,
            "source_port_id": ports["Bonny Terminal"].id,
            "destination_port_id": ports["Mangalore"].id,
            "corridor_id": corridors["Cape of Good Hope"].id,
            "cargo_volume_bbl": 1500000,
            "crude_grade": "Bonny Light",
            "eta": datetime(2026, 7, 22, 12, 30, tzinfo=UTC),
            "status": "planned",
            "freight_cost": 9100000,
            "risk_flag": False,
        },
    ]

    seeded: list[Shipment] = []
    for item in shipment_rows:
        seeded.append(upsert_by_lookup(db, Shipment, {"tanker_name": item["tanker_name"]}, item))
    return seeded


def seed_geopolitical_events(db: Session) -> list[GeopoliticalEvent]:
    events = [
        {
            "title": "Hormuz navigation warning issued",
            "event_type": "maritime_security",
            "region": "Persian Gulf",
            "source": "demo-intel",
            "summary": "Regional tensions trigger elevated alert levels for tanker transits.",
            "severity_score": 0.88,
            "event_time": datetime(2026, 7, 1, 6, 0, tzinfo=UTC),
            "extracted_entities": {"locations": ["Strait of Hormuz"], "actors": ["regional forces"]},
            "impact_tags": ["corridor_risk", "shipping_delay", "insurance_cost"],
        },
        {
            "title": "Red Sea attack risk remains elevated",
            "event_type": "conflict",
            "region": "Red Sea",
            "source": "demo-intel",
            "summary": "Commercial vessels face recurring threats near key chokepoints.",
            "severity_score": 0.79,
            "event_time": datetime(2026, 7, 2, 9, 30, tzinfo=UTC),
            "extracted_entities": {"locations": ["Red Sea"], "actors": ["non-state groups"]},
            "impact_tags": ["route_diversion", "logistics_cost", "port_congestion"],
        },
        {
            "title": "OPEC output guidance turns cautious",
            "event_type": "market",
            "region": "Global",
            "source": "demo-intel",
            "summary": "Supply-side caution raises the probability of tighter crude balances.",
            "severity_score": 0.58,
            "event_time": datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
            "extracted_entities": {"organizations": ["OPEC+"]},
            "impact_tags": ["price_spike", "supply_tightness"],
        },
    ]

    seeded: list[GeopoliticalEvent] = []
    for item in events:
        seeded.append(upsert_by_lookup(db, GeopoliticalEvent, {"title": item["title"]}, item))
    return seeded


def seed_sanctions_events(db: Session) -> list[SanctionsEvent]:
    events = [
        {
            "jurisdiction": "United States",
            "target_country": "Russia",
            "target_entity": "Shadow Fleet Operator A",
            "sanction_type": "shipping_restriction",
            "effective_date": date(2026, 7, 5),
            "severity_score": 0.94,
            "notes": "New restrictions on vessel insurance and servicing.",
        },
        {
            "jurisdiction": "European Union",
            "target_country": "Russia",
            "target_entity": "Trading Desk B",
            "sanction_type": "asset_freeze",
            "effective_date": date(2026, 7, 6),
            "severity_score": 0.91,
            "notes": "Expanded sanctions affecting trade finance and brokerage.",
        },
        {
            "jurisdiction": "United Kingdom",
            "target_country": "Iran",
            "target_entity": "Oil Transport Entity C",
            "sanction_type": "entity_designation",
            "effective_date": date(2026, 7, 8),
            "severity_score": 0.87,
            "notes": "Increased compliance burden for intermediaries and vessel operators.",
        },
    ]

    seeded: list[SanctionsEvent] = []
    for item in events:
        lookup = {
            "jurisdiction": item["jurisdiction"],
            "target_entity": item["target_entity"],
            "effective_date": item["effective_date"],
        }
        seeded.append(upsert_by_lookup(db, SanctionsEvent, lookup, item))
    return seeded


def seed_commodity_prices(db: Session) -> list[CommodityPrice]:
    prices = [
        {"benchmark_name": "Brent", "price_usd": 87.4, "timestamp": datetime(2026, 7, 3, 0, 0, tzinfo=UTC), "source": "demo-market"},
        {"benchmark_name": "Dubai", "price_usd": 84.1, "timestamp": datetime(2026, 7, 3, 0, 0, tzinfo=UTC), "source": "demo-market"},
        {"benchmark_name": "Oman", "price_usd": 85.0, "timestamp": datetime(2026, 7, 3, 0, 0, tzinfo=UTC), "source": "demo-market"},
        {
            "benchmark_name": "Indian Basket",
            "price_usd": 86.2,
            "timestamp": datetime(2026, 7, 3, 0, 0, tzinfo=UTC),
            "source": "demo-market",
        },
    ]

    seeded: list[CommodityPrice] = []
    for item in prices:
        lookup = {"benchmark_name": item["benchmark_name"], "timestamp": item["timestamp"]}
        seeded.append(upsert_by_lookup(db, CommodityPrice, lookup, item))
    return seeded


def seed_knowledge_documents(db: Session) -> list[dict[str, Any]]:
    documents = [
        {
            "title": "Hormuz transit risk note",
            "source_name": "demo-intel",
            "source_type": "analyst_note",
            "summary": "Assesses the sensitivity of Indian imports to Strait of Hormuz disruption.",
            "content_text": (
                "Indian crude import flows remain highly exposed to the Strait of Hormuz. "
                "A temporary closure or military escalation would likely force rapid rerouting via "
                "the Cape of Good Hope, raise voyage times, increase freight costs, and tighten "
                "prompt availability for coastal refineries. Tactical stock drawdown can cushion "
                "the first wave of supply loss, but procurement teams should pre-negotiate alternate "
                "Middle East and Atlantic cargoes."
            ),
            "metadata_json": {"topic": "hormuz", "priority": "high", "tags": ["corridor", "shipping", "india"]},
        },
        {
            "title": "Sanctions and shadow fleet briefing",
            "source_name": "demo-intel",
            "source_type": "analyst_note",
            "summary": "Summarizes how sanctions escalation can affect tanker availability and finance.",
            "content_text": (
                "Expanded sanctions on Russian and Iranian trading networks can reduce tanker availability, "
                "increase insurance costs, and create financing delays for liftings. The main operational risk "
                "is not only the loss of physical barrels but also slower settlement cycles, lower route optionality, "
                "and compliance-driven shipment reclassification. Diversified supplier baskets and clearer sanctions screening "
                "reduce execution risk."
            ),
            "metadata_json": {"topic": "sanctions", "priority": "high", "tags": ["sanctions", "compliance", "shipping"]},
        },
        {
            "title": "Refinery compatibility and crude slate note",
            "source_name": "demo-intel",
            "source_type": "analyst_note",
            "summary": "Notes which Indian refineries can flex between sour and sweet grades.",
            "content_text": (
                "Refineries with broader crude compatibility are better positioned to absorb disruptions by switching "
                "between Arab Light, Basrah Light, WTI, and similar grades. Complexity and port congestion affect how "
                "quickly the system can translate alternate procurement into throughput stability. Strategic reserves are "
                "most valuable when allocated to refineries that face immediate feedstock constraints and cannot quickly "
                "reshape slates."
            ),
            "metadata_json": {"topic": "refining", "priority": "medium", "tags": ["refinery", "compatibility", "spr"]},
        },
    ]

    seeded: list[dict[str, Any]] = []
    for item in documents:
        seeded.append(ingest_intelligence_document(db, KnowledgeDocumentCreateRequest(**item)))
    return seeded


def seed_risk_scores(
    db: Session,
    countries: dict[str, SupplierCountry],
    corridors: dict[str, ShippingCorridor],
    refineries: dict[str, Refinery],
) -> list[RiskScore]:
    scores = [
        {
            "scope_type": "corridor",
            "scope_id": str(corridors["Strait of Hormuz"].id),
            "risk_score": 0.92,
            "risk_level": "critical",
            "confidence_score": 0.9,
            "contributing_factors": {"geopolitics": 0.95, "shipping_density": 0.71, "insurance": 0.86},
        },
        {
            "scope_type": "corridor",
            "scope_id": str(corridors["Red Sea"].id),
            "risk_score": 0.84,
            "risk_level": "high",
            "confidence_score": 0.86,
            "contributing_factors": {"attack_frequency": 0.88, "reroute_cost": 0.79},
        },
        {
            "scope_type": "supplier",
            "scope_id": str(countries["Saudi Arabia"].id),
            "risk_score": 0.41,
            "risk_level": "medium",
            "confidence_score": 0.82,
            "contributing_factors": {"reliability": 0.91, "geopolitical": 0.46},
        },
        {
            "scope_type": "supplier",
            "scope_id": str(countries["Russia"].id),
            "risk_score": 0.89,
            "risk_level": "critical",
            "confidence_score": 0.93,
            "contributing_factors": {"sanctions": 0.94, "trade_finance": 0.85},
        },
        {
            "scope_type": "refinery",
            "scope_id": str(refineries["Jamnagar Refinery"].id),
            "risk_score": 0.36,
            "risk_level": "low",
            "confidence_score": 0.8,
            "contributing_factors": {"stock_cover": 0.74, "crude_flexibility": 0.88},
        },
        {
            "scope_type": "national",
            "scope_id": "india",
            "risk_score": 0.67,
            "risk_level": "high",
            "confidence_score": 0.84,
            "contributing_factors": {"import_dependence": 0.91, "route_risk": 0.83, "price_volatility": 0.72},
        },
    ]

    seeded: list[RiskScore] = []
    for item in scores:
        lookup = {"scope_type": item["scope_type"], "scope_id": item["scope_id"]}
        seeded.append(upsert_by_lookup(db, RiskScore, lookup, item))
    return seeded


def seed_scenarios(
    db: Session,
    creator: User,
    refineries: dict[str, Refinery],
) -> tuple[list[Scenario], list[ScenarioResult], list[ProcurementRecommendation], list[SPRPlan]]:
    scenario_1 = upsert_by_lookup(
        db,
        Scenario,
        {"name": "Hormuz closure - 14 day disruption"},
        {
            "scenario_type": "chokepoint_closure",
            "trigger_description": "Simulate a partial or full closure of the Strait of Hormuz for 14 days.",
            "assumptions": {
                "duration_days": 14,
                "reroute_fraction": 0.6,
                "spot_market_spike_pct": 18,
            },
            "duration_days": 14,
            "status": "ready",
            "created_by": creator.id,
        },
    )
    scenario_2 = upsert_by_lookup(
        db,
        Scenario,
        {"name": "Red Sea escalation + sanctions tightening"},
        {
            "scenario_type": "multi_factor_disruption",
            "trigger_description": "Combine Red Sea diversion risk with sanctions tightening on shadow fleet capacity.",
            "assumptions": {
                "duration_days": 21,
                "reroute_fraction": 0.8,
                "sanctions_intensity": "high",
            },
            "duration_days": 21,
            "status": "ready",
            "created_by": creator.id,
        },
    )

    scenario_results = [
        upsert_by_lookup(
            db,
            ScenarioResult,
            {"scenario_id": scenario_1.id},
            {
                "estimated_supply_loss_pct": 7.8,
                "refinery_utilization_impact": -4.2,
                "fuel_price_impact_pct": 12.5,
                "logistics_cost_impact_pct": 15.9,
                "gdp_impact_estimate": -0.18,
                "output_json": {
                    "key_assumptions": {"reroute_fraction": 0.6},
                    "notes": "Short disruption absorbed by commercial stocks and tactical rerouting.",
                },
            },
        ),
        upsert_by_lookup(
            db,
            ScenarioResult,
            {"scenario_id": scenario_2.id},
            {
                "estimated_supply_loss_pct": 11.6,
                "refinery_utilization_impact": -7.1,
                "fuel_price_impact_pct": 18.4,
                "logistics_cost_impact_pct": 21.7,
                "gdp_impact_estimate": -0.31,
                "output_json": {
                    "key_assumptions": {"reroute_fraction": 0.8, "sanctions_intensity": "high"},
                    "notes": "Combined effect drives higher freight and inventory drawdown.",
                },
            },
        ),
    ]

    recommendations = [
        upsert_by_lookup(
            db,
            ProcurementRecommendation,
            {"title": "Shift marginal cargoes toward UAE and West Africa"},
            {
                "scenario_id": scenario_1.id,
                "refinery_id": refineries["Jamnagar Refinery"].id,
                "recommended_supplier": "UAE + Nigeria blend",
                "recommended_route": "Cape of Good Hope",
                "expected_cost_delta": 4.8,
                "risk_reduction_score": 0.71,
                "compatibility_score": 0.84,
                "action_priority": "high",
                "recommendation_payload": {
                    "strategy": "reroute",
                    "reason": "Reduce exposure to Hormuz concentration risk.",
                },
            },
        ),
        upsert_by_lookup(
            db,
            ProcurementRecommendation,
            {"title": "Prioritize low-sulfur imports for coastal refineries"},
            {
                "scenario_id": scenario_2.id,
                "refinery_id": refineries["Paradip Refinery"].id,
                "recommended_supplier": "Saudi Arabia",
                "recommended_route": "Cape of Good Hope",
                "expected_cost_delta": 6.2,
                "risk_reduction_score": 0.64,
                "compatibility_score": 0.79,
                "action_priority": "medium",
                "recommendation_payload": {
                    "strategy": "blend_optimization",
                    "reason": "Maintain refinery throughput while corridors remain strained.",
                },
            },
        ),
    ]

    spr_plans = [
        upsert_by_lookup(
            db,
            SPRPlan,
            {"scenario_id": scenario_1.id},
            {
                "total_drawdown_bbl": 8200000,
                "drawdown_days": 14,
                "daily_release_schedule": {"day_1_7": 450000, "day_8_14": 385000},
                "replenishment_strategy": {
                    "phase_1": "Replace via prompt imports after corridor normalization",
                    "phase_2": "Top up using low-risk term cargoes",
                },
                "policy_notes": "Use SPR to offset short-term logistical disruptions and protect refinery runs.",
            },
        )
    ]

    return [scenario_1, scenario_2], scenario_results, recommendations, spr_plans


def seed_demo_data(create_tables: bool = True) -> None:
    """Seed the demo database with representative, repeatable sample data."""
    if create_tables:
        init_db()
    db = SessionLocal()
    try:
        users = seed_users(db)
        countries = seed_supplier_countries(db)
        corridors = seed_corridors(db)
        ports = seed_ports(db)
        refineries = seed_refineries(db, ports)
        seed_shipments(db, countries, corridors, ports)
        seed_geopolitical_events(db)
        seed_sanctions_events(db)
        seed_commodity_prices(db)
        seed_knowledge_documents(db)
        seed_risk_scores(db, countries, corridors, refineries)
        seed_scenarios(db, users["admin"], refineries)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo data for the energy resilience platform.")
    parser.add_argument(
        "--skip-create-tables",
        action="store_true",
        help="Skip table creation and only run the seed logic.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_demo_data(create_tables=not args.skip_create_tables)
    print("Demo data seeded successfully.")


if __name__ == "__main__":
    main()
