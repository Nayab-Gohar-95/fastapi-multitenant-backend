"""
api/routes/messages.py
----------------------
LLM messaging endpoints.

POST /messages         — Send prompt, get full response (stored in DB)
GET  /messages         — Paginated list of tenant messages
GET  /messages/stream  — Stream LLM response token by token (SSE)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.message import MessageCreate, MessageListResponse, MessageRead
from app.services.llm_service import llm_service
from app.services.message_service import MessageService

router = APIRouter(tags=["Messages"])


@router.post(
    "/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to the LLM (full response)",
)
async def send_message(
    body: MessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageRead:
    """
    Send a prompt to the LLM and receive the complete response.
    The exchange is stored in the database and tracked in MLflow.
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
    "/messages/stream",
    summary="Stream LLM response token by token (Server-Sent Events)",
    response_class=StreamingResponse,
)
async def stream_message(
    content: str = Query(..., min_length=1, max_length=8000,
                         description="Prompt to send to the LLM"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
):
    """
    Stream the LLM response as Server-Sent Events (SSE).

    Each chunk arrives as:   data: <token>\\n\\n
    End of stream:           data: [DONE]\\n\\n

    How to consume in a browser / frontend:
        const es = new EventSource('/messages/stream?content=Hello');
        es.onmessage = (e) => {
            if (e.data === '[DONE]') { es.close(); return; }
            document.getElementById('output').innerText += e.data;
        };

    How to test with curl:
        curl -N -H "Authorization: Bearer <token>" \\
          "http://localhost:8000/messages/stream?content=What+is+FastAPI"

    Note: Streamed responses are NOT stored in the database.
          Use POST /messages for persistent storage.
    """
    return StreamingResponse(
        llm_service.generate_stream(
            prompt=content,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
        ),
        media_type="text/event-stream",
        headers={
            # Prevent proxy/browser buffering — essential for streaming to work
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/messages",
    response_model=MessageListResponse,
    summary="List messages for the current tenant (paginated)",
)
async def list_messages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
) -> MessageListResponse:
    """Paginated list of all messages in the authenticated user's tenant."""
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
