"""
api/routes/messages.py
----------------------
LLM messaging endpoints.

POST /messages  — Send a prompt to the LLM; store and return the response.
GET  /messages  — Paginated list of messages for the authenticated user's tenant.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.message import MessageCreate, MessageListResponse, MessageRead
from app.services.message_service import MessageService

router = APIRouter(tags=["Messages"])


@router.post(
    "/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to the LLM",
)
async def send_message(
    body: MessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageRead:
    """
    Send a prompt to the LLM.

    - Requires authentication (any role).
    - The AI response is persisted alongside the original message.
    - tenant_id is sourced from the JWT — not from the request body.
    """
    try:
        message = await MessageService.create_message(
            db=db,
            content=body.content,
            user=current_user,
        )
        return MessageRead.model_validate(message)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        )


@router.get(
    "/messages",
    response_model=MessageListResponse,
    summary="List messages for the current tenant",
)
async def list_messages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
) -> MessageListResponse:
    """
    Returns a paginated list of all messages within the authenticated
    user's tenant. Users can see all tenant messages; this can be
    narrowed to user-only by adding `Message.user_id == current_user.id`
    to the service query.
    """
    total, messages = await MessageService.list_messages(
        db=db,
        user=current_user,
        skip=skip,
        limit=limit,
    )
    return MessageListResponse(
        total=total,
        items=[MessageRead.model_validate(m) for m in messages],
    )
