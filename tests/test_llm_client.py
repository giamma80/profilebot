from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from src.core.config import Settings
from src.core.llm.client import LLMDecisionClient
from src.core.llm.schemas import DecisionCandidate, LLMRequest


@dataclass
class _Call:
    model: str
    temperature: float
    max_tokens: int
    messages: list[dict[str, str]]
    response_format: dict[str, str]


class _FakeChatCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[_Call] = []

    def create(
        self,
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        messages: list[dict[str, str]],
        response_format: dict[str, str],
    ) -> Any:
        self.calls.append(
            _Call(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                response_format=response_format,
            )
        )
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeChatCompletions(content)


class _FakeOpenAI:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def _make_settings() -> Settings:
    return Settings(
        llm_provider="openai",
        llm_model="gpt-4",
        llm_base_url=None,
        llm_api_key="test-key",
        llm_temperature=0.2,
        llm_max_tokens=256,
    )


def _make_candidate(cv_id: str = "cv-1") -> DecisionCandidate:
    return DecisionCandidate(
        cv_id=cv_id,
        skills=["python", "fastapi"],
        seniority="senior",
        years_experience=5,
        availability_status="free",
        experience_summaries=["Backend Lead (2y)"],
    )


def test_complete__parses_decision_output() -> None:
    raw_response = (
        "{"
        '"selected_cv_id": "cv-1",'
        '"decision_reason": "Strong backend skill match.",'
        '"matched_skills": ["python", "fastapi"],'
        '"missing_skills": ["kubernetes"],'
        '"confidence": "high"'
        "}"
    )
    client = _FakeOpenAI(raw_response)
    settings = _make_settings()
    decision_client = LLMDecisionClient(client=client, settings=settings)

    request = LLMRequest(
        system_prompt="system",
        context="context",
        user_prompt="user",
        temperature=0.2,
        max_tokens=128,
    )

    result = decision_client.complete(request)

    assert result.selected_cv_id == "cv-1"
    assert result.confidence == "high"


def test_decide__builds_request_and_calls_chat() -> None:
    raw_response = (
        "{"
        '"selected_cv_id": "cv-1",'
        '"decision_reason": "Strong backend skill match.",'
        '"matched_skills": ["python"],'
        '"missing_skills": ["kubernetes"],'
        '"confidence": "medium"'
        "}"
    )
    client = _FakeOpenAI(raw_response)
    settings = _make_settings()
    decision_client = LLMDecisionClient(client=client, settings=settings)

    result = decision_client.decide([_make_candidate()])

    assert result.selected_cv_id == "cv-1"
    assert client.chat.completions.calls
    call = client.chat.completions.calls[0]
    assert call.model == "gpt-4"
    assert call.temperature == 0.2
    assert call.max_tokens == 256
    assert call.response_format == {"type": "json_object"}
    assert call.messages[0]["role"] == "system"
    assert call.messages[1]["role"] == "user"


def test_complete__empty_content_raises() -> None:
    client = _FakeOpenAI("")
    settings = _make_settings()
    decision_client = LLMDecisionClient(client=client, settings=settings)

    request = LLMRequest(
        system_prompt="system",
        context="context",
        user_prompt="user",
        temperature=0.2,
        max_tokens=128,
    )

    with pytest.raises(ValueError, match="content is empty"):
        decision_client.complete(request)
