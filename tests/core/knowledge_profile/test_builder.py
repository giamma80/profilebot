from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.core.knowledge_profile.builder import KPBuilder
from src.core.parser.schemas import CVMetadata, ExperienceItem, ParsedCV
from src.core.skills.dictionary import SkillDictionary, SkillDictionaryMeta, SkillEntry
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus


class _AvailabilityStub:
    def __init__(self, availability: ProfileAvailability | None) -> None:
        self._availability = availability

    def get(self, res_id: int) -> ProfileAvailability | None:
        return self._availability


class _AvailabilityFailingStub:
    def get(self, res_id: int) -> ProfileAvailability | None:
        raise RuntimeError("availability failure")


class _ReskillingStub:
    def __init__(self, record: ReskillingRecord | None) -> None:
        self._record = record

    def get(self, res_id: int) -> ReskillingRecord | None:
        return self._record


class _ReskillingFailingStub:
    def get(self, res_id: int) -> ReskillingRecord | None:
        raise RuntimeError("reskilling failure")


def _dictionary() -> SkillDictionary:
    meta = SkillDictionaryMeta(
        version="test",
        updated_at=None,
        domains=["backend", "devops", "data"],
    )
    skills = {
        "python": SkillEntry(
            canonical="python",
            domain="backend",
            aliases=["py"],
            related=["fastapi"],
            certifications=["pcap"],
        ),
        "kubernetes": SkillEntry(
            canonical="kubernetes",
            domain="devops",
            aliases=[],
            related=[],
            certifications=["cka"],
        ),
    }
    alias_map = {"py": skills["python"]}
    return SkillDictionary(meta, skills, alias_map)


def _parsed_cv() -> ParsedCV:
    metadata = CVMetadata(
        cv_id="cv-1",
        res_id=123,
        file_name="cv.pdf",
        full_name="Ada Lovelace",
        current_role="Backend Engineer",
        parsed_at=datetime.now(UTC),
    )
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Backend Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
            description="Built Python services with FastAPI and PostgreSQL.",
            is_current=False,
        ),
    ]
    return ParsedCV(
        metadata=metadata,
        skills=None,
        experiences=experiences,
        education=[],
        certifications=[],
        raw_text="",
    )


def _skill_result() -> SkillExtractionResult:
    return SkillExtractionResult(
        cv_id="cv-1",
        normalized_skills=[
            NormalizedSkill(
                original="Python",
                canonical="python",
                domain="backend",
                confidence=0.95,
                match_type="exact",
            )
        ],
        unknown_skills=["fortran"],
        dictionary_version="v1",
    )


def _availability() -> ProfileAvailability:
    return ProfileAvailability(
        res_id=123,
        status=AvailabilityStatus.FREE,
        allocation_pct=0,
        current_project=None,
        available_from=date(2024, 1, 1),
        available_to=None,
        manager_name="Manager",
        updated_at=datetime.now(UTC),
    )


def _reskilling() -> ReskillingRecord:
    return ReskillingRecord(
        res_id=123,
        course_name="Kubernetes Fundamentals",
        skill_target="kubernetes",
        status=ReskillingStatus.IN_PROGRESS,
        start_date=date(2024, 1, 1),
        end_date=None,
        provider="CloudAcademy",
        completion_pct=70,
    )


def test_kp_builder__full_data__builds_profile() -> None:
    builder = KPBuilder(
        availability_service=_AvailabilityStub(_availability()),
        reskilling_service=_ReskillingStub(_reskilling()),
        dictionary=_dictionary(),
    )

    profile = builder.build(
        cv_id="cv-1",
        res_id=123,
        parsed_cv=_parsed_cv(),
        skill_result=_skill_result(),
        query_skills=["python", "kubernetes", "aws"],
        match_score=0.82,
    )

    assert profile.cv_id == "cv-1"
    assert profile.res_id == 123
    assert profile.total_skills == 2
    assert profile.unknown_skills == ["fortran"]
    assert profile.availability is not None
    assert profile.availability.is_intercontratto is True
    assert profile.ic_sub_state is not None
    assert profile.reskilling_paths
    assert profile.has_active_reskilling is True
    assert profile.matched_skills == ["python", "kubernetes"]
    assert profile.missing_skills == ["aws"]
    assert profile.match_ratio == pytest.approx(2 / 3)
    assert profile.match_score == pytest.approx(0.82)


def test_kp_builder__graceful_degradation__returns_partial_profile() -> None:
    builder = KPBuilder(
        availability_service=_AvailabilityFailingStub(),
        reskilling_service=_ReskillingFailingStub(),
        dictionary=_dictionary(),
    )

    profile = builder.build(
        cv_id="cv-1",
        res_id=123,
        parsed_cv=_parsed_cv(),
        skill_result=_skill_result(),
    )

    assert profile.availability is None
    assert profile.reskilling_paths == []
    assert profile.has_active_reskilling is False


def test_kp_builder__minimal_inputs__still_builds_profile() -> None:
    builder = KPBuilder(
        availability_service=_AvailabilityStub(None),
        reskilling_service=_ReskillingStub(None),
        dictionary=_dictionary(),
    )

    profile = builder.build(
        cv_id="cv-1",
        res_id=123,
        parsed_cv=_parsed_cv(),
        skill_result=_skill_result(),
        query_skills=[],
    )

    assert profile.match_ratio == 0.0
    assert profile.matched_skills == []
    assert profile.missing_skills == []
