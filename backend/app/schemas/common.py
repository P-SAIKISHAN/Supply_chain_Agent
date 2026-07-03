from pydantic import BaseModel


class ORMBaseSchema(BaseModel):
    """Base schema configured for SQLAlchemy model serialization."""

    class Config:
        orm_mode = True
