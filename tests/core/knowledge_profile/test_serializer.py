from __future__ import annotations

from datetime import date

from src.core.knowledge_profile.schemas import (
    AvailabilityDetail,
    ExperienceSnapshot,
    KnowledgeProfile,
    RelevantChunk,
    ReskillingPath,
    SkillDetail,
)
from src.core.knowledge_profile.serializer import KPContextSerializer
from src.services.availability.schemas import AvailabilityStatus


def _profile() -> KnowledgeProfile:
    return KnowledgeProfile(
        cv_id="cv-1",
        res_id=123,
        full_name="Ada Lovelace",
        current_role="Backend Engineer",
        skills=[
            SkillDetail(
                canonical="python",
                domain="backend",
                confidence=0.95,
                match_type="exact",
                source="cv",
                reskilling_completion_pct=None,
                related_certifications=["pcap"],
                last_used_hint=None,
            ),
            SkillDetail(
                canonical="kubernetes",
                domain="devops",
                confidence=0.7,
                match_type="exact",
                source="reskilling",
                reskilling_completion_pct=70,
                related_certifications=["cka"],
                last_used_hint=None,
            ),
        ],
        skill_domains={"backend": 1, "devops": 1},
        total_skills=2,
        unknown_skills=[],
        seniority_bucket="mid",
        years_experience_estimate=4,
        availability=AvailabilityDetail(
            status=AvailabilityStatus.FREE,
            allocation_pct=0,
            current_project=None,
            available_from=date(2024, 1, 1),
            available_to=None,
            manager_name="Manager",
            is_intercontratto=True,
        ),
        ic_sub_state=None,
        reskilling_paths=[
            ReskillingPath(
                course_name="Kubernetes Fundamentals",
                target_skills=["kubernetes"],
                completion_pct=70,
                provider="CloudAcademy",
                start_date=date(2024, 1, 1),
                end_date=None,
                is_active=True,
            )
        ],
        has_active_reskilling=True,
        experiences=[
            ExperienceSnapshot(
                company="Acme",
                role="Backend Engineer",
                period="2020-2022",
                description_summary="Built Python services with FastAPI.",
                related_skills=["python"],
            )
        ],
        relevant_chunks=[
            RelevantChunk(
                text="Designed microservices with Kafka and Redis.",
                source_collection="cv_experiences",
                similarity_score=0.87,
                section_type="experience",
            )
        ],
        match_score=0.82,
        matched_skills=["python"],
        missing_skills=["aws"],
        match_ratio=0.5,
    )


def test_serialize_batch__matching__renders_expected_sections() -> None:
    serializer = KPContextSerializer(max_skills_per_domain=5, max_experiences=2, max_chunks=2)
    output = serializer.serialize_batch([_profile()], scenario="matching")

    assert "═══ CANDIDATO 1/1 ═══" in output
    assert "▸ SKILL MATCHATE" in output
    assert "▸ SKILL MANCANTI" in output
    assert "▸ TUTTE LE SKILL" in output
    assert "▸ DISPONIBILITÀ" in output
    assert "▸ RESKILLING ATTIVO" in output
    assert "▸ ESPERIENZE RILEVANTI" in output
    assert "▸ CHUNK CONTESTUALI" in output


def test_estimate_tokens__length_based__returns_quarter_length() -> None:
    text = "abcd" * 10
    assert KPContextSerializer.estimate_tokens(text) == len(text) // 4
