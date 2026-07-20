from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base for schemas that read straight off SQLAlchemy model instances."""

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
