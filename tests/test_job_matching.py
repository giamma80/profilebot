"""Tests for the job matching service."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.services.matching.job_analyzer import _parse_jd_analysis
from src.services.matching.matcher import (
    _build_candidates_context,
    _parse_ranking_output,
    _search_only_rank,
)
from src.services.matching.schemas import (
    JDAnalysis,
    JobMatchRequest,
    SkillRequirement,
)
from src.services.search.skill_search import ProfileMatch

# ──────────────────────────────────────────
# Schema tests
# ──────────────────────────────────────────


class TestJDAnalysis:
    def test_all_skills_combines_must_and_nice(self) -> None:
        jd = JDAnalysis(must_have=["python", "fastapi"], nice_to_have=["docker"])
        assert jd.all_skills == ["python", "fastapi", "docker"]

    def test_to_requirements_labels_importance(self) -> None:
        jd = JDAnalysis(must_have=["python"], nice_to_have=["docker"])
        reqs = jd.to_requirements()
        assert len(reqs) == 2
        assert reqs[0] == SkillRequirement(skill="python", importance="must_have")
        assert reqs[1] == SkillRequirement(skill="docker", importance="nice_to_have")

    def test_empty_skills(self) -> None:
        jd = JDAnalysis()
        assert jd.all_skills == []
        assert jd.to_requirements() == []


class TestJobMatchRequest:
    def test_valid_request(self) -> None:
        req = JobMatchRequest(
            job_description="Cerchiamo un backend developer Python con 3 anni di esperienza"
        )
        assert req.max_candidates == 5
        assert req.availability_filter == "free_or_partial"
        assert req.include_explanation is True

    def test_rejects_short_jd(self) -> None:
        with pytest.raises(ValidationError):
            JobMatchRequest(job_description="short")

    def test_custom_params(self) -> None:
        req = JobMatchRequest(
            job_description="Senior React developer needed for frontend project",
            max_candidates=3,
            availability_filter="only_free",
            include_explanation=False,
        )
        assert req.max_candidates == 3
        assert req.include_explanation is False


# ──────────────────────────────────────────
# JD Analysis parsing tests
# ──────────────────────────────────────────


class TestParseJDAnalysis:
    def test_valid_json_parses(self) -> None:
        raw = json.dumps(
            {
                "must_have": ["python", "fastapi"],
                "nice_to_have": ["docker", "kubernetes"],
                "seniority": "senior",
                "domain": "backend",
            }
        )
        result = _parse_jd_analysis(raw)
        assert result.must_have == ["python", "fastapi"]
        assert result.nice_to_have == ["docker", "kubernetes"]
        assert result.seniority == "senior"
        assert result.domain == "backend"

    def test_null_domain_is_none(self) -> None:
        raw = json.dumps(
            {
                "must_have": ["react"],
                "nice_to_have": [],
                "seniority": "mid",
                "domain": "null",
            }
        )
        result = _parse_jd_analysis(raw)
        assert result.domain is None

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="not valid JSON"):
            _parse_jd_analysis("not json")

    def test_fallback_parse_on_extra_fields(self) -> None:
        raw = json.dumps(
            {
                "must_have": ["python"],
                "nice_to_have": ["docker"],
                "seniority": "senior",
                "domain": "backend",
                "unexpected_field": "value",
            }
        )
        # extra="forbid" → fallback parse
        result = _parse_jd_analysis(raw)
        assert result.must_have == ["python"]

    def test_empty_skills_raises(self) -> None:
        raw = json.dumps(
            {
                "must_have": [],
                "nice_to_have": [],
                "seniority": "invalid",
                "domain": "invalid",
            }
        )
        with pytest.raises(ValueError, match="zero skills"):
            _parse_jd_analysis(raw)


# ──────────────────────────────────────────
# Candidates context building tests
# ──────────────────────────────────────────


def _make_profile_match(
    cv_id: str = "cv-1",
    res_id: int = 100001,
    score: float = 0.85,
) -> ProfileMatch:
    return ProfileMatch(
        cv_id=cv_id,
        res_id=res_id,
        score=score,
        matched_skills=["python", "fastapi"],
        missing_skills=["kubernetes"],
        skill_domain="backend",
        seniority="senior",
    )


class TestBuildCandidatesContext:
    def test_formats_single_candidate(self) -> None:
        ctx = _build_candidates_context([_make_profile_match()])
        assert "CV_ID: cv-1" in ctx
        assert "RES_ID: 100001" in ctx
        assert "SCORE: 0.85" in ctx
        assert "python, fastapi" in ctx
        assert "kubernetes" in ctx

    def test_formats_multiple_candidates(self) -> None:
        results = [
            _make_profile_match("cv-1", 100001, 0.90),
            _make_profile_match("cv-2", 100002, 0.75),
        ]
        ctx = _build_candidates_context(results)
        assert "Candidato 1" in ctx
        assert "Candidato 2" in ctx
        assert ctx.index("cv-1") < ctx.index("cv-2")


# ──────────────────────────────────────────
# Ranking output parsing tests
# ──────────────────────────────────────────


class TestParseRankingOutput:
    def test_parses_valid_ranking(self) -> None:
        raw = json.dumps(
            {
                "rankings": [
                    {
                        "cv_id": "cv-1",
                        "score": 0.92,
                        "matched_skills": ["python", "fastapi"],
                        "missing_skills": ["kubernetes"],
                        "explanation": "Strong backend match.",
                        "strengths": ["Python expert"],
                        "gaps": ["No K8s experience"],
                    },
                ]
            }
        )
        results = [_make_profile_match("cv-1")]
        candidates = _parse_ranking_output(raw, results, max_candidates=5)
        assert len(candidates) == 1
        assert candidates[0].cv_id == "cv-1"
        assert candidates[0].overall_score == 0.92
        assert "Python expert" in candidates[0].strengths

    def test_normalizes_score_100_to_01(self) -> None:
        raw = json.dumps({"rankings": [{"cv_id": "cv-1", "score": 85, "explanation": "Good."}]})
        results = [_make_profile_match("cv-1")]
        candidates = _parse_ranking_output(raw, results, max_candidates=5)
        assert candidates[0].overall_score == 0.85

    def test_skips_unknown_cv_id(self) -> None:
        raw = json.dumps(
            {
                "rankings": [
                    {"cv_id": "cv-unknown", "score": 0.9, "explanation": "?"},
                    {"cv_id": "cv-1", "score": 0.8, "explanation": "OK."},
                ]
            }
        )
        results = [_make_profile_match("cv-1")]
        candidates = _parse_ranking_output(raw, results, max_candidates=5)
        assert len(candidates) == 1
        assert candidates[0].cv_id == "cv-1"

    def test_respects_max_candidates(self) -> None:
        raw = json.dumps(
            {
                "rankings": [
                    {"cv_id": "cv-1", "score": 0.9, "explanation": "A"},
                    {"cv_id": "cv-2", "score": 0.8, "explanation": "B"},
                    {"cv_id": "cv-3", "score": 0.7, "explanation": "C"},
                ]
            }
        )
        results = [
            _make_profile_match("cv-1", 1),
            _make_profile_match("cv-2", 2),
            _make_profile_match("cv-3", 3),
        ]
        candidates = _parse_ranking_output(raw, results, max_candidates=2)
        assert len(candidates) == 2

    def test_handles_matched_alias(self) -> None:
        """LLM may use 'matched' instead of 'matched_skills'."""
        raw = json.dumps(
            {
                "rankings": [
                    {
                        "cv_id": "cv-1",
                        "score": 0.85,
                        "matched": ["python"],
                        "missing": ["docker"],
                        "explanation": "Alias fields.",
                    },
                ]
            }
        )
        results = [_make_profile_match("cv-1")]
        candidates = _parse_ranking_output(raw, results, max_candidates=5)
        assert candidates[0].matched_skills == ["python"]
        assert candidates[0].missing_skills == ["docker"]


# ──────────────────────────────────────────
# Search-only fallback tests
# ──────────────────────────────────────────


class TestSearchOnlyRank:
    def test_converts_matches_to_candidates(self) -> None:
        results = [
            _make_profile_match("cv-1", 100001, 0.90),
            _make_profile_match("cv-2", 100002, 0.75),
        ]
        candidates = _search_only_rank(results, max_candidates=5)
        assert len(candidates) == 2
        assert candidates[0].cv_id == "cv-1"
        assert candidates[0].explanation == ""

    def test_respects_max(self) -> None:
        results = [_make_profile_match(f"cv-{i}", i, 0.5) for i in range(10)]
        candidates = _search_only_rank(results, max_candidates=3)
        assert len(candidates) == 3
