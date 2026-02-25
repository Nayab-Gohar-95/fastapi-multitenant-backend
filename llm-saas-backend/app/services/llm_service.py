"""
services/llm_service.py
-----------------------
LLM abstraction layer.

Design:
  - LLMService is a thin async wrapper that isolates the application from
    the specific LLM provider.
  - The mock implementation returns deterministic responses and requires
    no external dependencies — useful for dev, CI, and unit tests.
  - Switching to OpenAI (or any other provider) requires only setting
    OPENAI_API_KEY in .env; no application code changes needed.

Extending to other providers:
  - Anthropic Claude:  Change client to anthropic.AsyncAnthropic()
  - Azure OpenAI:      Use openai.AsyncAzureOpenAI()
  - Local Ollama:      Use openai-compatible endpoint with base_url
"""

import time

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    Async LLM service.

    Usage:
        llm = LLMService()
        response = await llm.generate("Tell me about async Python")
    """

    def __init__(self) -> None:
        self._use_mock = not bool(settings.OPENAI_API_KEY)
        if not self._use_mock:
            # Lazy import so the package isn't required when mocking
            import openai
            self._client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.info(
                "LLMService initialised in MOCK mode — set OPENAI_API_KEY to use real LLM"
            )

    async def generate(self, prompt: str) -> str:
        """
        Generate a response for the given prompt.

        Args:
            prompt: User message / question.

        Returns:
            AI-generated response string.

        Raises:
            RuntimeError: If the LLM provider returns an error.
        """
        start = time.monotonic()

        if self._use_mock:
            response = await self._mock_generate(prompt)
        else:
            response = await self._openai_generate(prompt)

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info("LLM response generated", elapsed_ms=elapsed_ms, mock=self._use_mock)

        return response

    # ── Mock ──────────────────────────────────────────────────────────────────

    async def _mock_generate(self, prompt: str) -> str:
        """
        Deterministic mock response for development and testing.
        Mirrors the real interface so tests don't need patching.
        """
        return (
            f"[MOCK LLM RESPONSE]\n\n"
            f"You asked: '{prompt[:100]}{'...' if len(prompt) > 100 else ''}'\n\n"
            "This is a simulated AI response. To connect a real LLM, set "
            "OPENAI_API_KEY in your .env file and restart the server. "
            "The service layer supports OpenAI, Azure OpenAI, Anthropic Claude, "
            "and any OpenAI-compatible endpoint (e.g. Ollama, Together AI)."
        )

    # ── OpenAI ────────────────────────────────────────────────────────────────

    async def _openai_generate(self, prompt: str) -> str:
        """Call the OpenAI Chat Completions API."""
        try:
            completion = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful, accurate, and concise AI assistant "
                            "integrated into a multi-tenant SaaS platform."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI API error", error=str(exc))
            raise RuntimeError(f"LLM generation failed: {exc}") from exc


# ── Singleton ─────────────────────────────────────────────────────────────────
# Instantiated once at startup; reuses the same async HTTP connection pool.
llm_service = LLMService()
