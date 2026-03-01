"""Tests for the job matching service."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from src.core.config import Settings
from src.core.knowledge_profile.schemas import (
    AvailabilityDetail,
    ICSubState,
    KnowledgeProfile,
    SkillDetail,
)
from src.services.availability.schemas import AvailabilityStatus
from src.services.matching.candidate_ranker import (
    build_candidates_context_flat,
    build_candidates_context_structured,
    search_only_rank,
)
from src.services.matching.explainer import parse_ranking_output
from src.services.matching.job_analyzer import _parse_jd_analysis, analyze_job_description
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

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_jds"


def _load_jd_text(file_name: str) -> str:
    return (FIXTURES_DIR / file_name).read_text(encoding="utf-8")


class _FakeChatCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **_kwargs):
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeChatCompletions(content)


class _FakeOpenAI:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


class TestAnalyzeJDWithFixtures:
    @pytest.mark.parametrize(
        "case",
        [
            {
                "file_name": "backend_python.md",
                "must_have": ["python", "fastapi"],
                "nice_to_have": ["postgresql"],
                "seniority": "senior",
                "domain": "backend",
                "expected_skill": "python",
            },
            {
                "file_name": "data_engineer.md",
                "must_have": ["python", "sql"],
                "nice_to_have": ["airflow"],
                "seniority": "mid",
                "domain": "data",
                "expected_skill": "sql",
            },
            {
                "file_name": "devops.md",
                "must_have": ["docker", "terraform"],
                "nice_to_have": ["kubernetes"],
                "seniority": "senior",
                "domain": "devops",
                "expected_skill": "docker",
            },
            {
                "file_name": "frontend_react.md",
                "must_have": ["react", "typescript"],
                "nice_to_have": ["next.js"],
                "seniority": "mid",
                "domain": "frontend",
                "expected_skill": "react",
            },
            {
                "file_name": "fullstack.md",
                "must_have": ["react", "python"],
                "nice_to_have": ["docker"],
                "seniority": "mid",
                "domain": "fullstack",
                "expected_skill": "react",
            },
        ],
    )
    def test_analyze_job_description__fixtures__returns_skills(
        self,
        case: dict[str, object],
    ) -> None:
        jd_text = _load_jd_text(cast(str, case["file_name"]))
        payload = {
            "must_have": cast(list[str], case["must_have"]),
            "nice_to_have": cast(list[str], case["nice_to_have"]),
            "seniority": cast(str, case["seniority"]),
            "domain": cast(str, case["domain"]),
        }
        client = _FakeOpenAI(json.dumps(payload))

        result = analyze_job_description(jd_text, client=client)

        assert cast(str, case["expected_skill"]) in result.must_have
        assert result.domain == cast(str, case["domain"])


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
    payload: dict[str, object] | None = None,
) -> ProfileMatch:
    return ProfileMatch(
        cv_id=cv_id,
        res_id=res_id,
        score=score,
        matched_skills=["python", "fastapi"],
        missing_skills=["kubernetes"],
        skill_domain="backend",
        seniority="senior",
        payload=payload,
    )


def _fake_profile(cv_id: str = "cv-1", res_id: int = 100001) -> KnowledgeProfile:
    return KnowledgeProfile(
        cv_id=cv_id,
        res_id=res_id,
        full_name="Mario Rossi",
        current_role="Senior Engineer",
        skills=[
            SkillDetail(
                canonical="python",
                domain="backend",
                confidence=1.0,
                match_type="exact",
                source="cv",
                reskilling_completion_pct=None,
                related_certifications=[],
                last_used_hint=None,
            )
        ],
        skill_domains={"backend": 1},
        total_skills=1,
        unknown_skills=[],
        seniority_bucket="senior",
        years_experience_estimate=5,
        availability=AvailabilityDetail(
            status=AvailabilityStatus.FREE,
            allocation_pct=0,
            current_project=None,
            available_from=None,
            available_to=None,
            manager_name=None,
            is_intercontratto=True,
        ),
        ic_sub_state=ICSubState.IC_AVAILABLE,
        reskilling_paths=[],
        has_active_reskilling=False,
        experiences=[],
        relevant_chunks=[],
        match_score=0.9,
        matched_skills=["python"],
        missing_skills=[],
        match_ratio=1.0,
    )


class TestBuildCandidatesContextFlat:
    def test_formats_single_candidate(self) -> None:
        ctx = build_candidates_context_flat([_make_profile_match()])
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
        ctx = build_candidates_context_flat(results)
        assert "Candidato 1" in ctx
        assert "Candidato 2" in ctx
        assert ctx.index("cv-1") < ctx.index("cv-2")


class TestBuildCandidatesContextStructured:
    def test_renders_kp_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _build_from_search(self, **_kwargs) -> KnowledgeProfile:
            return _fake_profile()

        monkeypatch.setattr(
            "src.core.knowledge_profile.builder.KPBuilder.build_from_search",
            _build_from_search,
        )

        ctx = build_candidates_context_structured(
            jd_analysis=JDAnalysis(must_have=["python"]),
            search_results=[_make_profile_match()],
            settings=Settings(),
        )

        assert "═══ CANDIDATO 1/1 ═══" in ctx

    def test_fallbacks_to_flat_on_builder_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _build_from_search(self, **_kwargs) -> KnowledgeProfile:
            raise ValueError("old payload")

        monkeypatch.setattr(
            "src.core.knowledge_profile.builder.KPBuilder.build_from_search",
            _build_from_search,
        )

        ctx = build_candidates_context_structured(
            jd_analysis=JDAnalysis(must_have=["python"]),
            search_results=[_make_profile_match()],
            settings=Settings(),
        )

        assert "--- Candidato 1 ---" in ctx


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
        candidates = parse_ranking_output(raw, results, max_candidates=5)
        assert len(candidates) == 1
        assert candidates[0].cv_id == "cv-1"
        assert candidates[0].overall_score == 0.92
        assert "Python expert" in candidates[0].strengths

    def test_normalizes_score_100_to_01(self) -> None:
        raw = json.dumps({"rankings": [{"cv_id": "cv-1", "score": 85, "explanation": "Good."}]})
        results = [_make_profile_match("cv-1")]
        candidates = parse_ranking_output(raw, results, max_candidates=5)
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
        candidates = parse_ranking_output(raw, results, max_candidates=5)
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
        candidates = parse_ranking_output(raw, results, max_candidates=2)
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
        candidates = parse_ranking_output(raw, results, max_candidates=5)
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
        candidates = search_only_rank(results, max_candidates=5)
        assert len(candidates) == 2
        assert candidates[0].cv_id == "cv-1"
        assert candidates[0].explanation == ""

    def test_respects_max(self) -> None:
        results = [_make_profile_match(f"cv-{i}", i, 0.5) for i in range(10)]
        candidates = search_only_rank(results, max_candidates=3)
        assert len(candidates) == 3
