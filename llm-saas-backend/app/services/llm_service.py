"""
services/llm_service.py
-----------------------
LLM abstraction layer with MLflow experiment tracking.

Every inference is:
  1. Executed (mock or real OpenAI)
  2. Tracked in MLflow (latency, token estimates, tenant/user context)

To view tracked runs:
  mlflow ui --port 5001
  Open: http://localhost:5001
"""

import asyncio
import time
from typing import AsyncGenerator

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:

    def __init__(self) -> None:
        self._use_mock = not bool(settings.OPENAI_API_KEY)
        if not self._use_mock:
            import openai
            self._client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.info("LLMService in MOCK mode — set OPENAI_API_KEY for real LLM")

    # ── Standard (non-streaming) generate ────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        tenant_id: str = "unknown",
        user_id: str = "unknown",
    ) -> str:
        """
        Generate a full response for the given prompt.
        Automatically tracks the call in MLflow.
        """
        start = time.monotonic()

        if self._use_mock:
            response = await self._mock_generate(prompt)
        else:
            response = await self._openai_generate(prompt)

        latency_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info("LLM response generated", latency_ms=latency_ms, mock=self._use_mock)

        # Track in MLflow (non-blocking, never raises)
        from app.services.mlflow_service import track_llm_call
        track_llm_call(
            prompt=prompt,
            response=response,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
            user_id=user_id,
            mock=self._use_mock,
        )

        return response

    # ── Streaming generate ────────────────────────────────────────────────────

    async def generate_stream(
        self,
        prompt: str,
        tenant_id: str = "unknown",
        user_id: str = "unknown",
    ) -> AsyncGenerator[str, None]:
        """
        Stream the response token by token.

        Yields:
            Server-Sent Event formatted strings:  data: <token>\n\n
            Final message:                        data: [DONE]\n\n

        Usage in route:
            return StreamingResponse(
                llm_service.generate_stream(prompt),
                media_type="text/event-stream"
            )
        """
        start = time.monotonic()
        full_response = []

        if self._use_mock:
            async for token in self._mock_stream(prompt):
                full_response.append(token)
                yield f"data: {token}\n\n"
        else:
            async for token in self._openai_stream(prompt):
                full_response.append(token)
                yield f"data: {token}\n\n"

        # Signal end of stream (standard SSE convention)
        yield "data: [DONE]\n\n"

        latency_ms = round((time.monotonic() - start) * 1000, 1)
        complete_response = "".join(full_response)

        logger.info("LLM stream completed", latency_ms=latency_ms, mock=self._use_mock)

        # Track completed stream in MLflow
        from app.services.mlflow_service import track_llm_call
        track_llm_call(
            prompt=prompt,
            response=complete_response,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
            user_id=user_id,
            mock=self._use_mock,
        )

    # ── Mock implementations ──────────────────────────────────────────────────

    async def _mock_generate(self, prompt: str) -> str:
        return (
            f"[MOCK LLM RESPONSE]\n\n"
            f"You asked: '{prompt[:100]}{'...' if len(prompt) > 100 else ''}'\n\n"
            "This is a simulated AI response. Set OPENAI_API_KEY in .env to use a real LLM."
        )

    async def _mock_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Simulates token-by-token streaming with realistic delays."""
        tokens = [
            "[MOCK", " STREAM]\n\n",
            "You", " asked:", f" '{prompt[:60]}'\n\n",
            "Streaming", " response", " token", " by", " token.",
            " This", " simulates", " real", " LLM", " streaming.",
            " Set", " OPENAI_API_KEY", " in", " .env", " for", " live", " tokens.",
        ]
        for token in tokens:
            await asyncio.sleep(0.05)  # 50ms delay per token = realistic feel
            yield token

    # ── OpenAI implementations ────────────────────────────────────────────────

    async def _openai_generate(self, prompt: str) -> str:
        try:
            completion = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI API error", error=str(exc))
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    async def _openai_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        try:
            stream = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                stream=True,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    yield token
        except Exception as exc:
            logger.error("OpenAI stream error", error=str(exc))
            raise RuntimeError(f"LLM streaming failed: {exc}") from exc


# Singleton — shared across all requests
llm_service = LLMService()
