"""LLM-driven section classification for CV parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import Settings, get_settings
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.core.parser.schemas import SectionClassification

DEFAULT_PROMPT_PATH = Path("data/prompts/section_classification.yaml")


class SectionClassificationError(Exception):
    """Raised when LLM section classification fails."""


@dataclass(frozen=True)
class SectionClassificationPrompt:
    """Prompt configuration for LLM section classification."""

    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int


def load_section_classification_prompt(
    path: str | Path | None = None,
) -> SectionClassificationPrompt:
    """Load the section classification prompt template.

    Args:
        path: Optional path to the prompt YAML file.

    Returns:
        SectionClassificationPrompt with validated settings.

    Raises:
        SectionClassificationError: If the prompt file is missing or invalid.
    """
    file_path = Path(path) if path else DEFAULT_PROMPT_PATH
    if not file_path.exists():
        raise SectionClassificationError(f"Prompt file not found: {file_path}")

    try:
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise SectionClassificationError(f"Failed to read prompt file: {file_path}") from exc

    if not isinstance(payload, dict):
        raise SectionClassificationError("Prompt payload must be a YAML mapping")

    system_prompt = payload.get("system_prompt")
    user_prompt = payload.get("user_prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise SectionClassificationError("Prompt must include a non-empty system_prompt")
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise SectionClassificationError("Prompt must include a non-empty user_prompt")

    temperature = payload.get("temperature", 0.0)
    max_tokens = payload.get("max_tokens", 1500)

    if not isinstance(temperature, int | float):
        raise SectionClassificationError("Prompt temperature must be a number")
    if not isinstance(max_tokens, int) or max_tokens < 1:
        raise SectionClassificationError("Prompt max_tokens must be a positive integer")

    return SectionClassificationPrompt(
        system_prompt=system_prompt.strip(),
        user_prompt=user_prompt.strip(),
        temperature=float(temperature),
        max_tokens=max_tokens,
    )


def classify_sections(
    lines: list[str],
    raw_text: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    prompt_path: str | Path | None = None,
) -> SectionClassification:
    """Classify CV sections using the configured LLM prompt.

    Args:
        lines: Text lines extracted from the CV.
        raw_text: Full raw text extracted from the CV.
        settings: Optional application settings.
        client: Optional preconfigured OpenAI-compatible client.
        prompt_path: Optional path to the prompt YAML file.

    Returns:
        SectionClassification with sectioned lines.

    Raises:
        SectionClassificationError: If the LLM response is invalid.
    """
    resolved_settings = settings or get_settings()
    prompt = load_section_classification_prompt(prompt_path)
    llm_client = LLMDecisionClient(
        client=client or create_llm_client(resolved_settings),
        settings=resolved_settings,
    )

    context = "\n".join(lines).strip() or raw_text
    request = LLMRequest(
        system_prompt=prompt.system_prompt,
        context=context,
        user_prompt=prompt.user_prompt,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )

    raw_content = _call_llm_with_retry(llm_client, request)
    return parse_section_classification(raw_content)


def parse_section_classification(raw_content: str) -> SectionClassification:
    """Parse and validate the LLM output for section classification.

    Args:
        raw_content: Raw JSON string returned by the LLM.

    Returns:
        SectionClassification parsed from the response.

    Raises:
        SectionClassificationError: If JSON is invalid or schema mismatches.
    """
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise SectionClassificationError(
            "LLM section classification response is not valid JSON",
        ) from exc

    try:
        return cast(SectionClassification, SectionClassification.model_validate(payload))
    except ValidationError as exc:
        raise SectionClassificationError(
            "LLM section classification response does not match schema",
        ) from exc


@retry(
    retry=retry_if_exception_type(
        (APIConnectionError, APIError, APITimeoutError, RateLimitError),
    ),
    stop=stop_after_attempt(2),
    wait=wait_exponential(min=1, max=5),
)
def _call_llm_with_retry(llm_client: LLMDecisionClient, request: LLMRequest) -> str:
    """Call the LLM with retry for transient errors."""
    return llm_client.chat_completion_raw(request)


__all__ = [
    "SectionClassificationError",
    "SectionClassificationPrompt",
    "classify_sections",
    "load_section_classification_prompt",
    "parse_section_classification",
]
