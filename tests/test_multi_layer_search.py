from __future__ import annotations

from pathlib import Path

import pytest

from src.services.search import multi_layer
from src.services.search.chunk_search import ChunkSearchResponse
from src.services.search.skill_search import ProfileMatch, SkillSearchResponse


class DummyCounter:
    def __init__(self) -> None:
        self.value: float = 0.0

    def inc(self, amount: int | float = 1) -> None:
        self.value += amount


class SettingsStub:
    scoring_use_weighted = False


def _patch_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        multi_layer,
        "_normalize_query_skills",
        lambda skills, dictionary: [skill.strip().lower() for skill in skills],
    )

    def _load_dictionary(_: object) -> object:
        return object()

    def _resolve_dictionary_path() -> Path:
        return Path("dummy")

    def _get_settings() -> SettingsStub:
        return SettingsStub()

    monkeypatch.setattr(multi_layer, "load_skill_dictionary", _load_dictionary)
    monkeypatch.setattr(multi_layer, "_resolve_dictionary_path", _resolve_dictionary_path)
    monkeypatch.setattr(multi_layer, "get_settings", _get_settings)


def _make_skill_response(
    matches: list[ProfileMatch],
    *,
    fallback_activated: bool = False,
    recovered_skills: list[str] | None = None,
) -> SkillSearchResponse:
    return SkillSearchResponse(
        results=matches,
        total=len(matches),
        limit=10,
        offset=0,
        query_time_ms=5,
        candidates_by_skills=matches,
        fallback_activated=fallback_activated,
        recovered_skills=recovered_skills,
    )


def _make_chunk_response(matches: list[ProfileMatch]) -> ChunkSearchResponse:
    return ChunkSearchResponse(
        results=matches,
        total=len(matches),
        limit=10,
        offset=0,
        query_time_ms=5,
    )


def test_multi_layer_search__filters_by_eligibility__returns_only_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_metadata(monkeypatch)

    skill_matches = [
        ProfileMatch(
            res_id=1,
            cv_id="cv-1",
            score=0.9,
            matched_skills=["python", "fastapi"],
            missing_skills=[],
        ),
        ProfileMatch(
            res_id=2,
            cv_id="cv-2",
            score=0.8,
            matched_skills=["python"],
            missing_skills=["fastapi", "sql"],
        ),
    ]
    chunk_matches = [
        ProfileMatch(
            res_id=2,
            cv_id="cv-2",
            score=0.7,
            matched_skills=[],
            missing_skills=[],
        ),
        ProfileMatch(
            res_id=3,
            cv_id="cv-3",
            score=0.6,
            matched_skills=[],
            missing_skills=[],
        ),
    ]

    monkeypatch.setattr(
        multi_layer,
        "search_by_skills",
        lambda **_: _make_skill_response(skill_matches),
    )
    monkeypatch.setattr(
        multi_layer,
        "search_by_chunks",
        lambda **_: _make_chunk_response(chunk_matches),
    )

    response = multi_layer.multi_layer_search(
        skills=["Python", "FastAPI"],
        limit=10,
        offset=0,
    )

    assert response.no_match_reason is None
    assert response.candidates_fused is not None
    assert len(response.candidates_fused) == 1
    assert response.candidates_fused[0].cv_id == "cv-1"
    assert response.results == response.candidates_fused
    assert response.candidates_by_skills is not None
    assert response.candidates_by_chunks is not None
    assert len(response.candidates_by_skills) == 2
    assert len(response.candidates_by_chunks) == 2


def test_multi_layer_search__no_eligible_candidates__sets_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_metadata(monkeypatch)

    skill_matches = [
        ProfileMatch(
            res_id=10,
            cv_id="cv-10",
            score=0.4,
            matched_skills=["python"],
            missing_skills=["fastapi", "sql", "redis", "docker"],
        )
    ]

    monkeypatch.setattr(
        multi_layer,
        "search_by_skills",
        lambda **_: _make_skill_response(skill_matches),
    )
    monkeypatch.setattr(
        multi_layer,
        "search_by_chunks",
        lambda **_: _make_chunk_response([]),
    )

    response = multi_layer.multi_layer_search(
        skills=["Python", "FastAPI"],
        limit=10,
        offset=0,
    )

    assert response.no_match_reason == "below_eligibility_threshold"
    assert response.total == 0
    assert response.results == []
    assert response.candidates_fused == []


def test_multi_layer_search__increments_metrics_and_sets_fusion_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_metadata(monkeypatch)

    chunk_counter = DummyCounter()
    fusion_counter = DummyCounter()
    monkeypatch.setattr(multi_layer, "CHUNK_RESULTS", chunk_counter)
    monkeypatch.setattr(multi_layer, "FUSION_USED", fusion_counter)

    skill_matches = [
        ProfileMatch(
            res_id=7,
            cv_id="cv-7",
            score=0.9,
            matched_skills=["python"],
            missing_skills=[],
        )
    ]
    chunk_matches = [
        ProfileMatch(
            res_id=8,
            cv_id="cv-8",
            score=0.5,
            matched_skills=[],
            missing_skills=[],
        )
    ]

    monkeypatch.setattr(
        multi_layer,
        "search_by_skills",
        lambda **_: _make_skill_response(skill_matches),
    )
    monkeypatch.setattr(
        multi_layer,
        "search_by_chunks",
        lambda **_: _make_chunk_response(chunk_matches),
    )

    response = multi_layer.multi_layer_search(
        skills=["Python"],
        limit=10,
        offset=0,
    )

    assert chunk_counter.value == len(chunk_matches)
    assert fusion_counter.value == 1
    assert response.fusion_strategy == "rrf"
