"""Knowledge Profile builder and aggregation logic."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Protocol

from src.core.knowledge_profile.ic_sub_state import calculate_ic_sub_state
from src.core.knowledge_profile.schemas import (
    AvailabilityDetail,
    ExperienceSnapshot,
    KnowledgeProfile,
    ReskillingPath,
    SkillDetail,
)
from src.core.parser.schemas import ParsedCV
from src.core.seniority.calculator import (
    calculate_seniority_bucket,
    calculate_total_experience_years,
)
from src.core.skills.dictionary import SkillDictionary, load_skill_dictionary
from src.core.skills.schemas import SkillExtractionResult
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.availability.service import AvailabilityService
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus
from src.services.reskilling.service import ReskillingService

logger = logging.getLogger(__name__)

_DEFAULT_DICTIONARY_PATH = Path("data/skills_dictionary.yaml")
_DESCRIPTION_MAX_CHARS = 200


class AvailabilityServiceProtocol(Protocol):
    def get(self, res_id: int) -> ProfileAvailability | None: ...


class ReskillingServiceProtocol(Protocol):
    def get(self, res_id: int) -> ReskillingRecord | None: ...


class KPBuilder:
    """Builder for Knowledge Profile aggregation."""

    def __init__(
        self,
        availability_service: AvailabilityServiceProtocol | None = None,
        reskilling_service: ReskillingServiceProtocol | None = None,
        dictionary: SkillDictionary | None = None,
    ) -> None:
        self._availability_service = availability_service or AvailabilityService()
        self._reskilling_service = reskilling_service or ReskillingService()
        self._dictionary = dictionary or load_skill_dictionary(_DEFAULT_DICTIONARY_PATH)

    def build(  # noqa: PLR0913
        self,
        *,
        cv_id: str,
        res_id: int,
        parsed_cv: ParsedCV,
        skill_result: SkillExtractionResult,
        query_skills: Iterable[str] | None = None,
        match_score: float = 0.0,
    ) -> KnowledgeProfile:
        """Build a KnowledgeProfile from parsed data and extracted skills.

        Args:
            cv_id: CV identifier.
            res_id: Resource identifier.
            parsed_cv: Parsed CV data.
            skill_result: Skill extraction output.
            query_skills: Optional query skills for match metadata.
            match_score: Optional match score provided by upstream search.

        Returns:
            KnowledgeProfile instance.
        """
        availability = self._safe_get_availability(res_id)
        reskilling_records = self._safe_get_reskilling_records(res_id)
        reskilling_paths = self._build_reskilling_paths(reskilling_records)

        skills = self._build_skill_details(skill_result, reskilling_records)
        skill_domains = self._count_skill_domains(skills)

        years_experience = calculate_total_experience_years(parsed_cv.experiences)
        role_titles = [
            title
            for title in (
                parsed_cv.metadata.current_role,
                *[item.role for item in parsed_cv.experiences],
            )
            if title
        ]
        seniority_bucket = calculate_seniority_bucket(
            years_experience,
            skill_result.skill_count,
            role_titles,
        )

        matched_skills, missing_skills, match_ratio = self._build_match_stats(
            query_skills=query_skills,
            skills=skills,
        )

        ic_sub_state = calculate_ic_sub_state(
            availability,
            reskilling_records,
            is_in_transition=False,
        )

        return KnowledgeProfile(
            cv_id=cv_id,
            res_id=res_id,
            full_name=parsed_cv.metadata.full_name,
            current_role=parsed_cv.metadata.current_role,
            skills=skills,
            skill_domains=skill_domains,
            total_skills=len(skills),
            unknown_skills=skill_result.unknown_skills,
            seniority_bucket=seniority_bucket,
            years_experience_estimate=years_experience,
            availability=self._build_availability_detail(availability),
            ic_sub_state=ic_sub_state,
            reskilling_paths=reskilling_paths,
            has_active_reskilling=any(path.is_active for path in reskilling_paths),
            experiences=self._build_experiences(parsed_cv, skills),
            relevant_chunks=[],
            match_score=match_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            match_ratio=match_ratio,
        )

    def _safe_get_availability(self, res_id: int) -> ProfileAvailability | None:
        try:
            return self._availability_service.get(res_id)
        except Exception as exc:
            logger.warning("Availability lookup failed for res_id '%s': %s", res_id, exc)
            return None

    def _safe_get_reskilling_records(self, res_id: int) -> list[ReskillingRecord]:
        try:
            record = self._reskilling_service.get(res_id)
        except Exception as exc:
            logger.warning("Reskilling lookup failed for res_id '%s': %s", res_id, exc)
            return []
        return [record] if record is not None else []

    def _build_availability_detail(
        self,
        availability: ProfileAvailability | None,
    ) -> AvailabilityDetail | None:
        if availability is None:
            return None
        is_intercontratto = availability.allocation_pct == 0 and availability.status in (
            AvailabilityStatus.FREE,
            AvailabilityStatus.UNAVAILABLE,
        )
        return AvailabilityDetail(
            status=availability.status,
            allocation_pct=availability.allocation_pct,
            current_project=availability.current_project,
            available_from=availability.available_from,
            available_to=availability.available_to,
            manager_name=availability.manager_name,
            is_intercontratto=is_intercontratto,
        )

    def _build_reskilling_paths(
        self,
        records: Iterable[ReskillingRecord],
    ) -> list[ReskillingPath]:
        paths: list[ReskillingPath] = []
        for record in records:
            target_skills = [record.skill_target] if record.skill_target else []
            completion_pct = record.completion_pct or 0
            paths.append(
                ReskillingPath(
                    course_name=record.course_name,
                    target_skills=target_skills,
                    completion_pct=completion_pct,
                    provider=record.provider,
                    start_date=record.start_date,
                    end_date=record.end_date,
                    is_active=record.status == ReskillingStatus.IN_PROGRESS,
                )
            )
        return paths

    def _build_skill_details(
        self,
        skill_result: SkillExtractionResult,
        reskilling_records: Iterable[ReskillingRecord],
    ) -> list[SkillDetail]:
        skills: list[SkillDetail] = []
        for normalized in skill_result.normalized_skills:
            entry = self._dictionary.get_by_canonical(normalized.canonical)
            domain = entry.domain if entry else normalized.domain
            certifications = entry.certifications if entry else []
            skills.append(
                SkillDetail(
                    canonical=normalized.canonical,
                    domain=domain,
                    confidence=normalized.confidence,
                    match_type=normalized.match_type,
                    source="cv",
                    reskilling_completion_pct=None,
                    related_certifications=certifications,
                    last_used_hint=None,
                )
            )

        for record in reskilling_records:
            if not record.skill_target:
                continue
            canonical = record.skill_target.strip().lower()
            if not canonical:
                continue
            entry = self._dictionary.get_by_canonical(canonical)
            domain = entry.domain if entry else "unknown"
            certifications = entry.certifications if entry else []
            completion_pct = record.completion_pct or 0
            confidence = completion_pct / 100 if completion_pct else 0.0
            skills.append(
                SkillDetail(
                    canonical=canonical,
                    domain=domain,
                    confidence=confidence,
                    match_type="exact",
                    source="reskilling",
                    reskilling_completion_pct=completion_pct,
                    related_certifications=certifications,
                    last_used_hint=None,
                )
            )

        return skills

    def _count_skill_domains(self, skills: Iterable[SkillDetail]) -> dict[str, int]:
        counter = Counter(skill.domain for skill in skills if skill.domain)
        return dict(counter)

    def _build_match_stats(
        self,
        *,
        query_skills: Iterable[str] | None,
        skills: Iterable[SkillDetail],
    ) -> tuple[list[str], list[str], float]:
        if not query_skills:
            return [], [], 0.0
        normalized_query = [skill.strip().lower() for skill in query_skills if skill.strip()]
        if not normalized_query:
            return [], [], 0.0
        available = {skill.canonical for skill in skills}
        matched = [skill for skill in normalized_query if skill in available]
        missing = [skill for skill in normalized_query if skill not in available]
        match_ratio = len(matched) / len(normalized_query)
        return matched, missing, match_ratio

    def _build_experiences(
        self,
        parsed_cv: ParsedCV,
        skills: Iterable[SkillDetail],
    ) -> list[ExperienceSnapshot]:
        canonical_skills = [skill.canonical for skill in skills]
        snapshots: list[ExperienceSnapshot] = []
        for experience in parsed_cv.experiences:
            period = self._format_period(
                experience.start_date,
                experience.end_date,
                experience.is_current,
            )
            description_summary = self._summarize_description(experience.description)
            related_skills = self._extract_related_skills(
                experience.description,
                canonical_skills,
            )
            snapshots.append(
                ExperienceSnapshot(
                    company=experience.company,
                    role=experience.role,
                    period=period,
                    description_summary=description_summary,
                    related_skills=related_skills,
                )
            )
        return snapshots

    def _format_period(
        self,
        start_date: date | None,
        end_date: date | None,
        is_current: bool,
    ) -> str:
        if start_date and end_date:
            return f"{start_date.year}-{end_date.year}"
        if start_date and is_current:
            return f"{start_date.year}-oggi"
        if start_date:
            return f"{start_date.year}-"
        return "N/A"

    def _summarize_description(self, description: str) -> str:
        cleaned = description.strip()
        if not cleaned:
            return ""
        if len(cleaned) <= _DESCRIPTION_MAX_CHARS:
            return cleaned
        return f"{cleaned[:_DESCRIPTION_MAX_CHARS].rstrip()}..."

    def _extract_related_skills(
        self,
        description: str,
        canonical_skills: Iterable[str],
    ) -> list[str]:
        text = description.lower()
        related = [skill for skill in canonical_skills if skill in text]
        return list(dict.fromkeys(related))


__all__ = ["KPBuilder"]
