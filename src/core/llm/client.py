"""LLM client wrapper for decision making with OpenAI-compatible providers."""

from __future__ import annotations

import logging
import os
from typing import Any, cast

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AzureOpenAI,
    OpenAI,
    RateLimitError,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import Settings, get_settings
from src.core.llm.prompts import (
    build_context,
    build_system_prompt,
    build_user_prompt,
    parse_decision_output,
)
from src.core.llm.schemas import DecisionCandidate, DecisionOutput, LLMRequest

logger = logging.getLogger(__name__)


def create_llm_client(settings: Settings) -> OpenAI | AzureOpenAI:
    """Create an OpenAI-compatible client based on configured provider.

    Args:
        settings: Application settings.

    Returns:
        OpenAI-compatible client instance.
    """
    provider = settings.llm_provider.strip().lower()
    if provider == "azure":
        api_version = getattr(settings, "llm_api_version", None) or os.getenv(
            "AZURE_OPENAI_API_VERSION",
            "2024-02-01",
        )
        return AzureOpenAI(
            azure_endpoint=settings.llm_base_url or "",
            api_key=settings.llm_api_key,
            api_version=api_version,
        )

    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "ollama",
    )


class LLMDecisionClient:
    """LLM decision engine client wrapper."""

    def __init__(
        self,
        *,
        client: OpenAI | AzureOpenAI | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the decision client.

        Args:
            client: Optional preconfigured OpenAI-compatible client.
            settings: Optional settings instance.
        """
        self._settings = settings or get_settings()
        self._client = client or create_llm_client(self._settings)

    @retry(
        retry=retry_if_exception_type(
            (APIConnectionError, APIError, APITimeoutError, RateLimitError),
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
    )
    def complete(self, request: LLMRequest) -> DecisionOutput:
        """Execute a completion request and parse the decision output.

        Args:
            request: LLM request with prompts and parameters.

        Returns:
            Parsed DecisionOutput.
        """
        model = self._settings.llm_model
        logger.debug("Calling LLM model '%s' with temperature %s", model, request.temperature)
        content = self._chat_completion(
            model=model,
            system_prompt=request.system_prompt,
            user_prompt=_merge_context_and_prompt(request.context, request.user_prompt),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return cast(DecisionOutput, parse_decision_output(content))

    def decide(self, candidates: list[DecisionCandidate]) -> DecisionOutput:
        """Build prompts for candidates and return LLM decision output.

        Args:
            candidates: Shortlisted candidates for decision.

        Returns:
            DecisionOutput with selected candidate and reasoning.
        """
        request = LLMRequest(
            system_prompt=build_system_prompt(),
            context=build_context(candidates),
            user_prompt=build_user_prompt(),
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )
        return cast(DecisionOutput, self.complete(request))

    def _chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return _extract_message_content(response)


def _merge_context_and_prompt(context: str, user_prompt: str) -> str:
    return f"CONTEXT:\n{context}\n\nTASK:\n{user_prompt}".strip()


def _extract_message_content(response: Any) -> str:
    message = response.choices[0].message
    content = message.content if message else None
    if not content:
        raise ValueError("LLM response content is empty")
    return str(content)


__all__ = ["LLMDecisionClient", "create_llm_client"]
