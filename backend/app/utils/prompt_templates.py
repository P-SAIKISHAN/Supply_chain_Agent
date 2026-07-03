from __future__ import annotations

from typing import Any


def scenario_summary_prompt(context: dict[str, Any]) -> str:
    scenario = context.get("scenario", {})
    result = context.get("result", {})
    notes = context.get("notes", [])
    citations = context.get("citations", [])
    return (
        "Write a concise operational scenario summary for Indian energy planners.\n"
        f"Scenario name: {scenario.get('name')}\n"
        f"Scenario type: {scenario.get('scenario_type')}\n"
        f"Trigger: {scenario.get('trigger_description')}\n"
        f"Estimated supply loss: {result.get('estimated_supply_loss_pct', 0.0)}%\n"
        f"Refinery utilization impact: {result.get('refinery_utilization_impact', 0.0)}%\n"
        f"Fuel price impact: {result.get('fuel_price_impact_pct', 0.0)}%\n"
        f"Mitigation urgency: {context.get('mitigation_urgency_level', 'moderate')}\n"
        f"Retrieved intelligence notes: {len(notes)}\n"
        f"Citations available: {len(citations)}\n"
        "Focus on actionable risk drivers, likely response measures, and what changed most recently."
    )


def procurement_summary_prompt(context: dict[str, Any]) -> str:
    recommendation = context.get("recommendation", {})
    notes = context.get("notes", [])
    return (
        "Write a concise procurement justification for a recommended import alternative.\n"
        f"Title: {recommendation.get('title')}\n"
        f"Supplier: {recommendation.get('recommended_supplier')}\n"
        f"Route: {recommendation.get('recommended_route')}\n"
        f"Overall score: {recommendation.get('overall_score', 0.0)}\n"
        f"Cost delta: {recommendation.get('expected_cost_delta', 0.0)}\n"
        f"Delivery delay: {recommendation.get('delivery_delay_days', 0.0)} days\n"
        f"Relevant notes: {len(notes)}\n"
        "Explain why the option is ranked well, what risk it reduces, and the main trade-offs."
    )


def risk_brief_prompt(context: dict[str, Any]) -> str:
    hotspots = context.get("hotspots", [])
    recent_events = context.get("recent_events", [])
    return (
        "Draft a short geopolitical risk brief for an energy supply chain dashboard.\n"
        f"National risk score: {context.get('national_score', 0.0)}\n"
        f"National risk level: {context.get('national_level', 'low')}\n"
        f"Hotspots: {len(hotspots)}\n"
        f"Recent events: {len(recent_events)}\n"
        "Highlight the top corridors, suppliers, and disruptions requiring attention."
    )


def format_bullet_summary(title: str, bullets: list[str], citations: list[dict[str, Any]] | None = None) -> str:
    lines = [title]
    for bullet in bullets:
        lines.append(f"- {bullet}")
    if citations:
        lines.append("Sources:")
        for citation in citations:
            label = citation.get("title") or citation.get("source_name") or "source"
            score = citation.get("score")
            lines.append(f"- {label} ({score})")
    return "\n".join(lines)

