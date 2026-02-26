"""
services/message_service.py
----------------------------
Business logic for LLM message creation and retrieval.
tenant_id is always enforced at query level — no cross-tenant leakage.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.message import Message
from app.models.user import User
from app.services.llm_service import llm_service

logger = get_logger(__name__)


class MessageService:

    @staticmethod
    async def create_message(
        db: AsyncSession,
        content: str,
        user: User,
    ) -> Message:
        """Call the LLM, persist the exchange, return the Message record."""
        logger.info(
            "Generating LLM response",
            user_id=user.id,
            tenant_id=user.tenant_id,
            prompt_length=len(content),
        )

        # Pass tenant_id and user_id so MLflow can track per-tenant usage
        ai_response = await llm_service.generate(
            prompt=content,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )

        message = Message(
            content=content,
            response=ai_response,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)

        logger.info("Message stored", message_id=message.id)
        return message

    @staticmethod
    async def list_messages(
        db: AsyncSession,
        user: User,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[Message]]:
        """Paginated message list scoped strictly to the requesting user's tenant."""
        base_filter = Message.tenant_id == user.tenant_id

        count_result = await db.execute(
            select(func.count()).select_from(Message).where(base_filter)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(Message)
            .where(base_filter)
            .order_by(Message.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return total, list(result.scalars().all())
