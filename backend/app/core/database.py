from collections.abc import Generator
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import settings


logger = logging.getLogger(__name__)


def _build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine tuned for production-style usage."""
    engine_kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    if database_url.startswith("sqlite"):
        engine_kwargs.pop("pool_pre_ping", None)
        engine_kwargs.pop("pool_recycle", None)
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    try:
        return create_engine(database_url, **engine_kwargs)
    except ModuleNotFoundError:
        fallback_url = "sqlite:///./energy_resilience.db"
        logger.warning(
            "postgres_driver_missing_falling_back_to_sqlite",
            extra={"requested_url": database_url, "fallback_url": fallback_url},
        )
        return create_engine(
            fallback_url,
            future=True,
            connect_args={"check_same_thread": False},
        )


engine = _build_engine(settings.database_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_database(db: Session) -> bool:
    """Lightweight database connectivity check used by readiness endpoints."""
    db.execute(text("SELECT 1"))
    return True


def init_db() -> None:
    """Create database tables for local development and demo environments.

    In production, prefer Alembic migrations. This helper keeps the project
    self-bootstrapping for hackathon/demo use cases.
    """
    # Import models so SQLAlchemy registers every table before create_all runs.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
