from __future__ import annotations

from datetime import date, datetime, timezone


UTC = timezone.utc


def news_items() -> list[dict]:
    return [
        {
            "title": "Hormuz navigation warning issued",
            "event_type": "maritime_security",
            "region": "Persian Gulf",
            "source": "demo-newswire",
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
            "source": "demo-newswire",
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
            "source": "demo-newswire",
            "summary": "Supply-side caution raises the probability of tighter crude balances.",
            "severity_score": 0.58,
            "event_time": datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
            "extracted_entities": {"organizations": ["OPEC+"]},
            "impact_tags": ["price_spike", "supply_tightness"],
        },
    ]


def sanctions_items() -> list[dict]:
    return [
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


def ais_items() -> list[dict]:
    return [
        {
            "tanker_name": "MT Horizon Star",
            "supplier_country": "Saudi Arabia",
            "source_port": "Ras Tanura",
            "destination_port": "Vadinar",
            "corridor": "Strait of Hormuz",
            "cargo_volume_bbl": 2000000,
            "crude_grade": "Arab Light",
            "eta": datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
            "status": "in_transit",
            "freight_cost": 8400000,
            "risk_flag": False,
        },
        {
            "tanker_name": "MT Basrah Pearl",
            "supplier_country": "Iraq",
            "source_port": "Basra Oil Terminal",
            "destination_port": "Paradip",
            "corridor": "Strait of Hormuz",
            "cargo_volume_bbl": 1800000,
            "crude_grade": "Basrah Light",
            "eta": datetime(2026, 7, 15, 15, 0, tzinfo=UTC),
            "status": "planned",
            "freight_cost": 7600000,
            "risk_flag": True,
        },
        {
            "tanker_name": "MT Desh Navigator",
            "supplier_country": "UAE",
            "source_port": "Fujairah",
            "destination_port": "Mumbai",
            "corridor": "Red Sea",
            "cargo_volume_bbl": 1600000,
            "crude_grade": "Murban",
            "eta": datetime(2026, 7, 18, 8, 0, tzinfo=UTC),
            "status": "scheduled",
            "freight_cost": 6900000,
            "risk_flag": False,
        },
    ]


def price_items() -> list[dict]:
    ts = datetime(2026, 7, 3, 0, 0, tzinfo=UTC)
    return [
        {"benchmark_name": "Brent", "price_usd": 87.4, "timestamp": ts, "source": "demo-market"},
        {"benchmark_name": "Dubai", "price_usd": 84.1, "timestamp": ts, "source": "demo-market"},
        {"benchmark_name": "Oman", "price_usd": 85.0, "timestamp": ts, "source": "demo-market"},
        {"benchmark_name": "Indian Basket", "price_usd": 86.2, "timestamp": ts, "source": "demo-market"},
    ]


def refinery_items() -> list[dict]:
    return [
        {
            "name": "Jamnagar Refinery",
            "company": "Reliance Industries",
            "state": "Gujarat",
            "capacity_bpd": 1240000,
            "complexity_index": 14.2,
            "compatible_crude_grades": ["Arab Light", "Arab Medium", "Basrah Light", "Bonny Light"],
            "linked_port_name": "Vadinar",
            "strategic_priority_score": 0.98,
        },
        {
            "name": "Paradip Refinery",
            "company": "Indian Oil Corporation",
            "state": "Odisha",
            "capacity_bpd": 300000,
            "complexity_index": 11.8,
            "compatible_crude_grades": ["Arab Light", "Basrah Light", "WTI"],
            "linked_port_name": "Paradip",
            "strategic_priority_score": 0.87,
        },
    ]

