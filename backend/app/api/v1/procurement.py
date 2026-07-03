from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.procurement import (
    ProcurementRecommendRequest,
    ProcurementRecommendResponse,
    ProcurementRecommendationListResponse,
    ProcurementRecommendationResponse,
)
from app.services.audit_service import safe_record_audit_log
from app.services.procurement_service import (
    generate_procurement_recommendations,
    get_procurement_recommendation,
    list_procurement_recommendations,
)

router = APIRouter(prefix="/procurement", tags=["procurement"])


@router.post("/recommend", response_model=ProcurementRecommendResponse, summary="Generate procurement alternatives")
def recommend(
    payload: ProcurementRecommendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = generate_procurement_recommendations(db, payload)
        safe_record_audit_log(
            db,
            user_id=current_user.id,
            action="recommendation_generated",
            entity_type="procurement_batch",
            entity_id=f"{payload.target_scope}:{payload.scenario_id or payload.refinery_id or 'national'}",
            metadata={
                "target_scope": payload.target_scope,
                "scenario_id": payload.scenario_id,
                "refinery_id": payload.refinery_id,
                "generated_count": result.get("generated_count", 0),
            },
            commit=True,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/recommendations", response_model=ProcurementRecommendationListResponse, summary="List procurement recommendations")
def recommendations(
    limit: int = Query(50, ge=1, le=200),
    scenario_id: int | None = None,
    refinery_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcurementRecommendationListResponse:
    return list_procurement_recommendations(
        db,
        limit=limit,
        scenario_id=scenario_id,
        refinery_id=refinery_id,
    )


@router.get("/recommendations/{recommendation_id}", response_model=ProcurementRecommendationResponse, summary="Get a procurement recommendation")
def recommendation(
    recommendation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcurementRecommendationResponse:
    try:
        return get_procurement_recommendation(db, recommendation_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
