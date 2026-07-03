from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse, UserCreate
from app.schemas.common import model_from_orm


class AuthenticationError(ValueError):
    """Raised when credentials are invalid or a token cannot be issued."""


class UserAlreadyExistsError(ValueError):
    """Raised when attempting to create a user with an existing email."""


def normalize_email(email: str) -> str:
    """Normalize email addresses for consistent storage and lookup."""
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return a user by email address, or None if not found."""
    statement = select(User).where(User.email == normalize_email(email))
    return db.scalar(statement)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Return a user by primary key, or None if not found."""
    return db.get(User, user_id)


def create_user(db: Session, user_in: UserCreate) -> User:
    """Create a new user after validating uniqueness of the email."""
    normalized_email = normalize_email(user_in.email)
    existing_user = get_user_by_email(db, normalized_email)
    if existing_user is not None:
        raise UserAlreadyExistsError("A user with this email already exists")

    user = User(
        full_name=user_in.full_name.strip(),
        email=normalized_email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserAlreadyExistsError("A user with this email already exists") from exc

    db.refresh(user)
    return user


def authenticate_user(db: Session, credentials: LoginRequest) -> User:
    """Validate login credentials and return the active user."""
    user = get_user_by_email(db, credentials.email)
    if user is None or not verify_password(credentials.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user


def create_token_for_user(user: User) -> str:
    """Issue a signed JWT for the authenticated user."""
    return create_access_token(
        subject=user.email,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        additional_claims={"role": user.role, "user_id": user.id},
    )


def build_token_response(user: User) -> TokenResponse:
    """Create the response payload returned after successful authentication."""
    return TokenResponse(
        access_token=create_token_for_user(user),
        user=model_from_orm(CurrentUserResponse, user),
    )
