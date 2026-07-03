try:  # Pydantic v2
    from pydantic import BaseModel, ConfigDict

    class APIBaseModel(BaseModel):
        """Application-wide base model with conservative defaults."""

        model_config = ConfigDict(extra="ignore")

    class ORMBaseSchema(APIBaseModel):
        """Base schema configured for SQLAlchemy model serialization."""

        model_config = ConfigDict(from_attributes=True, extra="ignore")

except ImportError:  # Pydantic v1 fallback for local environments
    from pydantic import BaseModel

    class APIBaseModel(BaseModel):
        """Application-wide base model with conservative defaults."""

        class Config:
            extra = "ignore"

    class ORMBaseSchema(APIBaseModel):
        """Base schema configured for SQLAlchemy model serialization."""

        class Config(APIBaseModel.Config):
            orm_mode = True
            extra = "ignore"


class PageMeta(APIBaseModel):
    """Reusable pagination metadata block."""

    total_count: int
    limit: int
    offset: int
    page: int
    pages: int
    sort_by: str | None = None
    sort_order: str | None = None


def model_from_orm(schema_cls, obj):
    """Serialize an ORM object in a Pydantic-version-safe way."""
    if hasattr(schema_cls, "model_validate"):
        return schema_cls.model_validate(obj)
    return schema_cls.from_orm(obj)
