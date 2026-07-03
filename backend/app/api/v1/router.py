from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.procurement import router as procurement_router
from app.api.v1.spr import router as spr_router
from app.api.v1.risks import router as risks_router
from app.api.v1.scenarios import router as scenarios_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(procurement_router)
api_router.include_router(spr_router)
api_router.include_router(risks_router)
api_router.include_router(scenarios_router)
api_router.include_router(health_router)
