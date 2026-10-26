"""Validated candidate onboarding data and detached API responses."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    current_role: str | None = Field(default=None, min_length=1, max_length=200)
    experience_years: Decimal | None = Field(
        default=None, ge=0, max_digits=4, decimal_places=1, allow_inf_nan=False
    )


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str | None
    current_role: str | None
    experience_years: Decimal | None

    @field_serializer("experience_years", when_used="json")
    def serialize_experience(self, value: Decimal | None) -> str | None:
        return format(value, ".1f") if value is not None else None
