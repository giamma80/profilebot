from __future__ import annotations

import json

import pytest

from src.services.search.schemas import SearchContext
from src.services.search.search_context import extract_search_context
from src.services.search.search_context_fallback import build_fallback_search_context


def test_extract_search_context__llm_response__returns_parsed_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_payload = json.dumps(
        {
            "extracted_skills": ["python", "fastapi"],
            "seniority": "senior",
            "availability_required": True,
            "domain": "backend",
            "role": "developer",
            "business_context": "Progetto banking",
            "raw_query": "ignored",
        }
    )

    def _chat_completion_raw(self, request):  # type: ignore[no-untyped-def]
        return response_payload

    monkeypatch.setattr(
        "src.services.search.search_context.LLMDecisionClient.chat_completion_raw",
        _chat_completion_raw,
    )

    result = extract_search_context("cerco un senior python disponibile")

    assert result is not None
    assert result.extracted_skills == ["python", "fastapi"]
    assert result.seniority == "senior"
    assert result.availability_required is True
    assert result.domain == "backend"
    assert result.role == "developer"
    assert result.business_context == "Progetto banking"
    assert result.raw_query == "cerco un senior python disponibile"


def test_extract_search_context__llm_timeout__uses_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _chat_completion_raw(self, request):  # type: ignore[no-untyped-def]
        raise TimeoutError("timeout")

    def _fallback(query: str) -> SearchContext:
        return SearchContext(
            extracted_skills=["python"],
            seniority="senior",
            availability_required=None,
            domain="backend",
            role=None,
            business_context=None,
            raw_query=query,
        )

    monkeypatch.setattr(
        "src.services.search.search_context.LLMDecisionClient.chat_completion_raw",
        _chat_completion_raw,
    )
    monkeypatch.setattr(
        "src.services.search.search_context.build_fallback_search_context",
        _fallback,
    )

    result = extract_search_context("senior python backend")

    assert result is not None
    assert result.extracted_skills == ["python"]
    assert result.role is None
    assert result.business_context is None
    assert result.raw_query == "senior python backend"


def test_build_fallback_search_context__role_and_business_context_are_null() -> None:
    result = build_fallback_search_context("cerco senior python disponibile")

    assert result.role is None
    assert result.business_context is None
