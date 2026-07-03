from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core import database as database_module
from app.core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    import redis as redis_lib
except ImportError:  # pragma: no cover - optional during local development
    redis_lib = None


@dataclass
class StartupCheckResult:
    database_ready: bool
    redis_ready: bool
    initialized_tables: bool
    strict: bool
    warnings: list[str]


def _check_database() -> tuple[bool, str | None]:
    db = database_module.SessionLocal()
    try:
        database_module.ping_database(db)
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        db.close()


def _check_redis() -> tuple[bool, str | None]:
    if not settings.redis_url:
        return True, None
    if redis_lib is None:
        return False, "redis package is not installed"

    try:
        client = redis_lib.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        ready = bool(client.ping())
        client.close()
        return ready, None
    except Exception as exc:  # pragma: no cover - external service check
        return False, str(exc)


def verify_startup_dependencies() -> StartupCheckResult:
    """Check core runtime dependencies and initialize tables in demo/dev modes."""
    warnings: list[str] = []
    db_ready, db_error = _check_database()
    if not db_ready and settings.environment in {"staging", "production"} and settings.startup_check_strict:
        raise RuntimeError(f"Database unavailable: {db_error}")
    if not db_ready:
        warnings.append(f"database_unavailable: {db_error}")
        logger.warning("startup_database_unavailable", extra={"error": db_error})

    initialized_tables = False
    if settings.demo_mode or settings.environment != "production":
        try:
            database_module.init_db()
            initialized_tables = True
        except Exception as exc:
            if settings.environment in {"staging", "production"} and settings.startup_check_strict:
                raise RuntimeError(f"Failed to initialize database tables: {exc}") from exc
            warnings.append(f"init_db_failed: {exc}")
            logger.warning("startup_init_db_failed", extra={"error": str(exc)})

    redis_ready, redis_error = _check_redis()
    if not redis_ready and settings.environment in {"staging", "production"} and settings.startup_check_strict:
        raise RuntimeError(f"Redis unavailable: {redis_error}")
    if not redis_ready:
        warnings.append(f"redis_unavailable: {redis_error}")
        logger.warning("startup_redis_unavailable", extra={"error": redis_error})

    if settings.environment == "production" and settings.secret_key == "change-me-in-production":
        warnings.append("secret_key_uses_default_placeholder")
        logger.warning("startup_secret_key_placeholder_in_use")

    return StartupCheckResult(
        database_ready=db_ready,
        redis_ready=redis_ready,
        initialized_tables=initialized_tables,
        strict=settings.startup_check_strict,
        warnings=warnings,
    )
