"""
services/message_service.py
----------------------------
Business logic for LLM message creation and retrieval.

Critical security invariant:
  Every query MUST include tenant_id in the WHERE clause.
  This prevents cross-tenant data leakage even if user_id is somehow guessable.
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
        """
        Call the LLM, persist the exchange, and return the Message record.

        The tenant_id is taken from the authenticated user's record so it
        can never be spoofed by a client-supplied value.
        """
        logger.info(
            "Generating LLM response",
            user_id=user.id,
            tenant_id=user.tenant_id,
            prompt_length=len(content),
        )

        ai_response = await llm_service.generate(content)

        message = Message(
            content=content,
            response=ai_response,
            user_id=user.id,
            tenant_id=user.tenant_id,  # Sourced from authenticated session
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)

        logger.info("Message stored", message_id=message.id, tenant_id=user.tenant_id)
        return message

    @staticmethod
    async def list_messages(
        db: AsyncSession,
        user: User,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[Message]]:
        """
        Paginated message list, strictly scoped to the requesting user's tenant.

        Returns:
            (total_count, page_of_messages)
        """
        base_filter = Message.tenant_id == user.tenant_id

        # Count query
        count_result = await db.execute(
            select(func.count()).select_from(Message).where(base_filter)
        )
        total = count_result.scalar_one()

        # Data query — ordered newest-first
        result = await db.execute(
            select(Message)
            .where(base_filter)
            .order_by(Message.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        messages = list(result.scalars().all())

        return total, messages
