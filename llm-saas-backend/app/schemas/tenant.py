"""
schemas/tenant.py
-----------------
Pydantic request/response models for Tenant.

Naming convention:
  TenantCreate  → inbound request body
  TenantRead    → outbound response body (never exposes internal fields)
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TenantCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        examples=["Acme Corp"],
        description="Unique company / tenant name",
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class TenantRead(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
