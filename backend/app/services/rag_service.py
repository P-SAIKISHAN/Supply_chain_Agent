from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import utcnow
from app.models.commodity_price import CommodityPrice
from app.models.geopolitical_event import GeopoliticalEvent
from app.models.intelligence_chunk import IntelligenceChunk
from app.models.intelligence_document import IntelligenceDocument
from app.models.port import Port
from app.models.recommendation import ProcurementRecommendation as ProcurementRecommendationModel
from app.models.risk_score import RiskScore
from app.models.sanctions_event import SanctionsEvent
from app.models.scenario import Scenario, ScenarioResult
from app.models.shipment import Shipment
from app.models.shipping_corridor import ShippingCorridor
from app.models.supplier_country import SupplierCountry
from app.schemas.reports import (
    ExplanationRequest,
    KnowledgeChunkResponse,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentResponse,
    ReportResponse,
    RiskBriefResponse,
    SourceCitationResponse,
)
from app.services.dashboard_service import get_latest_alerts
from app.services.procurement_service import get_procurement_recommendation
from app.services.risk_service import get_risk_overview
from app.utils.llm import generate_text, llm_configured
from app.utils.prompt_templates import (
    format_bullet_summary,
    procurement_summary_prompt,
    risk_brief_prompt,
    scenario_summary_prompt,
)


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _chunk_text(text: str, chunk_size: int = 140, overlap: int = 30) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words).strip()]

    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_size]
        if chunk:
            chunks.append(" ".join(chunk).strip())
        if start + chunk_size >= len(words):
            break
    return chunks


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _document_response(document: IntelligenceDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "title": document.title,
        "source_name": document.source_name,
        "source_type": document.source_type,
        "url": document.url,
        "external_id": document.external_id,
        "summary": document.summary,
        "content_text": document.content_text,
        "published_at": document.published_at,
        "metadata_json": document.metadata_json or {},
        "chunk_count": document.chunk_count,
        "content_hash": document.content_hash,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def ingest_intelligence_document(db: Session, payload: KnowledgeDocumentCreateRequest) -> dict[str, Any]:
    """Store a source document and split it into retrievable chunks."""
    content_hash = _hash_text((payload.title or "") + "\n" + payload.content_text)
    lookup = {}
    if payload.external_id:
        lookup["external_id"] = payload.external_id
    else:
        lookup["content_hash"] = content_hash

    document = db.query(IntelligenceDocument).filter_by(**lookup).one_or_none()
    if document is None:
        document = IntelligenceDocument(
            title=payload.title,
            source_name=payload.source_name,
            source_type=payload.source_type,
            url=payload.url,
            external_id=payload.external_id,
            summary=payload.summary,
            content_text=payload.content_text,
            published_at=payload.published_at,
            metadata_json=payload.metadata_json,
            chunk_count=0,
            content_hash=content_hash,
        )
        db.add(document)
        db.flush()
    else:
        document.title = payload.title
        document.source_name = payload.source_name
        document.source_type = payload.source_type
        document.url = payload.url
        document.summary = payload.summary
        document.content_text = payload.content_text
        document.published_at = payload.published_at
        document.metadata_json = payload.metadata_json
        document.content_hash = content_hash
        document.chunks.clear()
        db.flush()

    chunks = _chunk_text(payload.content_text)
    for index, chunk_text in enumerate(chunks):
        db.add(
            IntelligenceChunk(
                document_id=document.id,
                chunk_index=index,
                chunk_text=chunk_text,
                chunk_hash=_hash_text(f"{document.id}:{index}:{chunk_text[:120]}"),
                token_count=len(chunk_text.split()),
                metadata_json={
                    "title": payload.title,
                    "source_name": payload.source_name,
                    "source_type": payload.source_type,
                    **(payload.metadata_json or {}),
                },
            )
        )

    document.chunk_count = len(chunks)
    db.commit()
    db.refresh(document)
    return _document_response(document)


def search_intelligence_notes(
    db: Session,
    query: str,
    top_k: int = 5,
    source_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank document chunks using a deterministic lexical overlap score."""
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return []

    documents = db.query(IntelligenceDocument).all()
    results: list[dict[str, Any]] = []
    for document in documents:
        if source_types and document.source_type not in source_types:
            continue
        doc_tokens = set(_tokenize(f"{document.title} {document.summary or ''} {document.content_text[:1200]}"))
        document_boost = len(query_tokens.intersection(doc_tokens)) * 3.0
        if document.external_id:
            document_boost += 1.0
        for chunk in document.chunks:
            chunk_tokens = set(_tokenize(chunk.chunk_text))
            overlap = len(query_tokens.intersection(chunk_tokens))
            if overlap == 0 and document_boost <= 0:
                continue
            score = (
                overlap * 4.0
                + len(query_tokens.intersection(doc_tokens)) * 1.5
                + min(1.5, chunk.token_count / 200.0)
                + document_boost
            )
            excerpt = chunk.chunk_text[:260].strip()
            if len(chunk.chunk_text) > 260:
                excerpt += "..."
            results.append(
                {
                    "document_id": document.id,
                    "chunk_id": chunk.id,
                    "title": document.title,
                    "source_name": document.source_name,
                    "source_type": document.source_type,
                    "score": round(score, 2),
                    "excerpt": excerpt,
                    "metadata_json": {
                        **(document.metadata_json or {}),
                        **(chunk.metadata_json or {}),
                    },
                    "published_at": document.published_at,
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def _scenario_context(db: Session, scenario_id: int, top_k_notes: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if scenario is None:
        raise KeyError(f"Scenario {scenario_id} not found")

    result = db.query(ScenarioResult).filter(ScenarioResult.scenario_id == scenario_id).one_or_none()
    scenario_dict = {
        "id": scenario.id,
        "name": scenario.name,
        "scenario_type": scenario.scenario_type,
        "trigger_description": scenario.trigger_description,
        "assumptions": _as_dict(scenario.assumptions),
        "duration_days": scenario.duration_days,
        "status": scenario.status,
    }
    result_dict = {
        "estimated_supply_loss_pct": float(result.estimated_supply_loss_pct or 0.0) if result else 0.0,
        "refinery_utilization_impact": float(result.refinery_utilization_impact or 0.0) if result else 0.0,
        "fuel_price_impact_pct": float(result.fuel_price_impact_pct or 0.0) if result else 0.0,
        "logistics_cost_impact_pct": float(result.logistics_cost_impact_pct or 0.0) if result else 0.0,
        "gdp_impact_estimate": float(result.gdp_impact_estimate or 0.0) if result else 0.0,
        "mitigation_urgency_level": _as_dict(result.output_json).get("mitigation_urgency_level") if result else None,
    }
    query = f"{scenario.name} {scenario.scenario_type} {scenario.trigger_description} {scenario.assumptions}"
    notes = search_intelligence_notes(db, query=query, top_k=top_k_notes)
    return {"scenario": scenario_dict, "result": result_dict}, notes


def _procurement_context(db: Session, recommendation_id: int, top_k_notes: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    recommendation = get_procurement_recommendation(db, recommendation_id)
    payload = recommendation.recommendation_payload or {}
    query = " ".join(
        [
            recommendation.title,
            recommendation.recommended_supplier,
            recommendation.recommended_route,
            payload.get("scenario_name") or "",
            payload.get("corridor_name") or "",
            payload.get("refinery_name") or "",
        ]
    )
    notes = search_intelligence_notes(db, query=query, top_k=top_k_notes)
    return {
        "recommendation": recommendation.dict(),
        "score_breakdown": payload.get("score_breakdown", {}),
    }, notes


def _fallback_summary(title: str, bullets: list[str], citations: list[dict[str, Any]], model_used: str) -> dict[str, Any]:
    return {
        "title": title,
        "summary": format_bullet_summary(title, bullets, citations=citations),
        "generated_at": utcnow(),
        "model_used": model_used,
        "citations": citations,
    }


def generate_scenario_summary(db: Session, scenario_id: int, use_llm: bool = True, top_k_notes: int = 5) -> dict[str, Any]:
    context, notes = _scenario_context(db, scenario_id, top_k_notes)
    scenario = context["scenario"]
    result = context["result"]
    citations = [
        SourceCitationResponse(**note).dict()
        for note in notes
    ]
    structured_context = {
        "scenario": scenario,
        "result": result,
        "mitigation_urgency_level": result.get("mitigation_urgency_level") or "moderate",
        "notes": notes,
        "citations": citations,
    }

    prompt = scenario_summary_prompt(structured_context)
    llm_text = generate_text(prompt, system_prompt="You are an energy intelligence analyst." ) if use_llm else None
    if llm_text:
        return {
            "title": f"Scenario Summary: {scenario['name']}",
            "summary": llm_text,
            "generated_at": utcnow(),
            "model_used": "llm" if llm_configured() else "template",
            "citations": citations,
            "structured_context": structured_context,
        }

    bullets = [
        f"Scenario type: {scenario['scenario_type']}",
        f"Trigger: {scenario['trigger_description']}",
        f"Supply loss estimate: {result.get('estimated_supply_loss_pct', 0.0):.1f}%",
        f"Refinery impact: {result.get('refinery_utilization_impact', 0.0):.1f}%",
        f"Mitigation urgency: {structured_context['mitigation_urgency_level']}",
    ]
    if notes:
        bullets.append(f"Top referenced note: {notes[0]['title']} from {notes[0]['source_name']}")
    return _fallback_summary(f"Scenario Summary: {scenario['name']}", bullets, citations, "template")


def generate_procurement_summary(db: Session, recommendation_id: int, use_llm: bool = True, top_k_notes: int = 5) -> dict[str, Any]:
    context, notes = _procurement_context(db, recommendation_id, top_k_notes)
    recommendation = context["recommendation"]
    citations = [SourceCitationResponse(**note).dict() for note in notes]
    structured_context = {
        "recommendation": recommendation,
        "score_breakdown": context.get("score_breakdown", {}),
        "notes": notes,
        "citations": citations,
    }
    prompt = procurement_summary_prompt(structured_context)
    llm_text = generate_text(prompt, system_prompt="You explain procurement alternatives for energy planners.") if use_llm else None
    if llm_text:
        return {
            "title": f"Procurement Summary: {recommendation['title']}",
            "summary": llm_text,
            "generated_at": utcnow(),
            "model_used": "llm" if llm_configured() else "template",
            "citations": citations,
            "structured_context": structured_context,
        }

    bullets = [
        f"Supplier: {recommendation['recommended_supplier']}",
        f"Route: {recommendation['recommended_route']}",
        f"Overall score: {recommendation.get('overall_score', 0.0):.1f}",
        f"Expected cost delta: {recommendation.get('expected_cost_delta', 0.0):.1f}",
        f"Delivery delay: {recommendation.get('delivery_delay_days', 0.0):.1f} days",
    ]
    if notes:
        bullets.append(f"Top referenced note: {notes[0]['title']} from {notes[0]['source_name']}")
    return _fallback_summary(f"Procurement Summary: {recommendation['title']}", bullets, citations, "template")


def generate_risk_brief(db: Session, use_llm: bool = True, top_k_notes: int = 5) -> dict[str, Any]:
    overview = get_risk_overview(db)
    alerts = get_latest_alerts(db, limit=top_k_notes)
    hotspots = search_intelligence_notes(
        db,
        query="India crude oil corridor supplier disruption sanctions shipping risks",
        top_k=top_k_notes,
    )
    citations = [SourceCitationResponse(**note).dict() for note in hotspots]
    structured_context = {
        "national_score": overview["national_score"],
        "national_level": overview["national_level"],
        "hotspots": hotspots,
        "recent_events": alerts,
        "citations": citations,
    }
    prompt = risk_brief_prompt(structured_context)
    llm_text = generate_text(prompt, system_prompt="You write concise risk briefs for policymakers.") if use_llm else None
    if llm_text:
        return {
            "title": "National Risk Brief",
            "summary": llm_text,
            "generated_at": utcnow(),
            "model_used": "llm" if llm_configured() else "template",
            "citations": citations,
            "structured_context": structured_context,
            "scope": "national",
        }

    bullets = [
        f"National risk score: {overview['national_score']:.1f} ({overview['national_level']})",
        f"Top risk scope: {overview.get('highest_risk_scope', {}).get('scope_type', 'n/a')}",
        f"Recent high-severity alerts: {len(alerts)}",
        f"Retrieved intelligence notes: {len(hotspots)}",
    ]
    if alerts:
        bullets.append(f"Latest alert: {alerts[0]['title']} ({alerts[0]['region']})")
    return {
        "scope": "national",
        **_fallback_summary("National Risk Brief", bullets, citations, "template"),
        "structured_context": structured_context,
    }
