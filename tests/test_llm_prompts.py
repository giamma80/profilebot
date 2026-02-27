from __future__ import annotations

import json

import pytest

from src.core.llm.prompts import (
    build_context,
    build_system_prompt,
    build_user_prompt,
    parse_decision_output,
)
from src.core.llm.schemas import DecisionCandidate


def _make_candidate(cv_id: str = "cv-1") -> DecisionCandidate:
    return DecisionCandidate(
        cv_id=cv_id,
        skills=["python", "fastapi"],
        seniority="senior",
        years_experience=5,
        availability_status="free",
        experience_summaries=["Backend Lead (2y)", "API Engineer (3y)"],
    )


def test_build_system_prompt__contains_skill_first_guidance() -> None:
    prompt = build_system_prompt()

    assert "skill" in prompt.lower()
    assert "cv_id" in prompt
    assert "json" in prompt.lower()


def test_build_user_prompt__mentions_expected_fields() -> None:
    prompt = build_user_prompt()

    assert "selected_cv_id" in prompt
    assert "decision_reason" in prompt
    assert "matched_skills" in prompt
    assert "missing_skills" in prompt
    assert "confidence" in prompt


def test_build_context__formats_candidate_block() -> None:
    candidate = _make_candidate()
    context = build_context([candidate])

    assert "CV_ID: cv-1" in context
    assert "SKILLS: python, fastapi" in context
    assert "SENIORITY: senior" in context
    assert "YEARS_EXPERIENCE: 5" in context
    assert "AVAILABILITY: free" in context
    assert "EXPERIENCES (support):" in context
    assert "* Backend Lead (2y)" in context
    assert "* API Engineer (3y)" in context


def test_build_context__orders_candidates_as_provided() -> None:
    first = _make_candidate("cv-1")
    second = _make_candidate("cv-2")

    context = build_context([first, second])

    assert context.index("CV_ID: cv-1") < context.index("CV_ID: cv-2")


def test_build_context__uses_na_for_empty_skills() -> None:
    candidate = DecisionCandidate(
        cv_id="cv-3",
        skills=[],
        seniority="junior",
        years_experience=2,
        availability_status="free",
        experience_summaries=["Junior Engineer (2y)"],
    )

    context = build_context([candidate])

    assert "SKILLS: N/A" in context


def test_build_context__uses_na_for_missing_experience() -> None:
    candidate = DecisionCandidate(
        cv_id="cv-2",
        skills=["react"],
        seniority="mid",
        years_experience=None,
        availability_status="partial",
        experience_summaries=[],
    )

    context = build_context([candidate])

    assert "YEARS_EXPERIENCE: N/A" in context
    assert "EXPERIENCES (support):" in context
    assert "* N/A" in context


def test_build_context__rejects_empty_candidates() -> None:
    with pytest.raises(ValueError, match="At least one candidate"):
        build_context([])


def test_build_context__rejects_more_than_seven_candidates() -> None:
    candidates = [_make_candidate(f"cv-{idx}") for idx in range(1, 9)]

    with pytest.raises(ValueError, match="more than 7"):
        build_context(candidates)


def test_build_context__rejects_duplicate_cv_ids() -> None:
    candidates = [_make_candidate("cv-1"), _make_candidate("cv-1")]

    with pytest.raises(ValueError, match="Duplicate cv_id"):
        build_context(candidates)


def test_parse_decision_output__valid_json_returns_model() -> None:
    payload = {
        "selected_cv_id": "cv-1",
        "decision_reason": "Strong backend skill match.",
        "matched_skills": ["python", "fastapi"],
        "missing_skills": ["kubernetes"],
        "confidence": "high",
    }
    raw = json.dumps(payload)

    result = parse_decision_output(raw)

    assert result.selected_cv_id == "cv-1"
    assert result.confidence == "high"


def test_parse_decision_output__invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_decision_output("not-json")


def test_parse_decision_output__schema_mismatch_raises() -> None:
    payload = {"selected_cv_id": "cv-1"}
    raw = json.dumps(payload)

    with pytest.raises(ValueError, match="DecisionOutput schema"):
        parse_decision_output(raw)
