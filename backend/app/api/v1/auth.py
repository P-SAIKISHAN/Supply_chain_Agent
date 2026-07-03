from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse, UserCreate
from app.schemas.common import model_from_orm
from app.services.audit_service import safe_record_audit_log, user_login_audit_metadata
from app.services.auth_service import (
    AuthenticationError,
    UserAlreadyExistsError,
    authenticate_user,
    build_token_response,
    create_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a new user and return an access token."""
    try:
        user = create_user(db, user_in)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return build_token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate a user",
)
def login(credentials: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Validate credentials and return an access token."""
    try:
        user = authenticate_user(db, credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token_response = build_token_response(user)
    safe_record_audit_log(
        db,
        user_id=user.id,
        action="user_login",
        entity_type="user",
        entity_id=str(user.id),
        metadata=user_login_audit_metadata(user),
        commit=True,
    )
    return token_response


@router.get("/me", response_model=CurrentUserResponse, summary="Get current user")
def me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """Return the authenticated user's profile."""
    return model_from_orm(CurrentUserResponse, current_user)
