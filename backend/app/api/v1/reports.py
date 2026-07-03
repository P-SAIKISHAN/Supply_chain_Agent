from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.reports import (
    ExplanationRequest,
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentResponse,
    ReportResponse,
    RiskBriefResponse,
)
from app.services.rag_service import (
    generate_procurement_summary,
    generate_risk_brief,
    generate_scenario_summary,
    ingest_intelligence_document,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/knowledge", response_model=KnowledgeDocumentResponse, summary="Store a knowledge document")
def ingest_knowledge(
    payload: KnowledgeDocumentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return ingest_intelligence_document(db, payload)


@router.post("/scenario-summary/{scenario_id}", response_model=ReportResponse, summary="Generate a scenario summary report")
def scenario_summary(
    scenario_id: int,
    payload: ExplanationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        options = payload or ExplanationRequest()
        return generate_scenario_summary(db, scenario_id, use_llm=options.use_llm, top_k_notes=options.top_k_notes)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/procurement-summary/{recommendation_id}",
    response_model=ReportResponse,
    summary="Generate a procurement summary report",
)
def procurement_summary(
    recommendation_id: int,
    payload: ExplanationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        options = payload or ExplanationRequest()
        return generate_procurement_summary(db, recommendation_id, use_llm=options.use_llm, top_k_notes=options.top_k_notes)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/risk-brief", response_model=RiskBriefResponse, summary="Generate a national risk brief")
def risk_brief(
    use_llm: bool = Query(True),
    top_k_notes: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return generate_risk_brief(db, use_llm=use_llm, top_k_notes=top_k_notes)

