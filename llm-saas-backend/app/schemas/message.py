"""
schemas/message.py
------------------
Pydantic models for LLM message exchange.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        examples=["What are the main benefits of async programming?"],
        description="User prompt sent to the LLM",
    )


class MessageRead(BaseModel):
    id: str
    content: str
    response: str
    user_id: str
    tenant_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    total: int
    items: list[MessageRead]
