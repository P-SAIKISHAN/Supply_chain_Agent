from pydantic import BaseModel, ConfigDict


class ORMBaseSchema(BaseModel):
    """Base schema configured for SQLAlchemy model serialization."""

    model_config = ConfigDict(from_attributes=True)

