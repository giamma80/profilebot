"""Knowledge Profile context serializer for LLM consumption."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.knowledge_profile.schemas import KnowledgeProfile, SkillDetail


@dataclass(frozen=True)
class KPContextSerializerConfig:
    """Configuration for KP context serialization."""

    max_skills_per_domain: int = 10
    max_experiences: int = 3
    max_chunks: int = 3
    max_chunk_chars: int = 300


class KPContextSerializer:
    """Serialize KnowledgeProfile data for the matching scenario."""

    def __init__(
        self,
        *,
        max_skills_per_domain: int = 10,
        max_experiences: int = 3,
        max_chunks: int = 3,
        max_chunk_chars: int = 300,
    ) -> None:
        self._max_skills_per_domain = max_skills_per_domain
        self._max_experiences = max_experiences
        self._max_chunks = max_chunks
        self._max_chunk_chars = max_chunk_chars

    def serialize(self, profile: KnowledgeProfile, *, index: int = 1, total: int = 1) -> str:
        """Serialize a single KnowledgeProfile into a structured text block.

        Args:
            profile: KnowledgeProfile to serialize.
            index: Candidate index in batch (1-based).
            total: Total candidates in batch.

        Returns:
            Serialized text block for the profile.
        """
        lines = [f"═══ CANDIDATO {index}/{total} ═══"]
        lines.append(f"ID: {profile.cv_id} | Res: {profile.res_id}")
        lines.append(f"Nome: {profile.full_name or 'N/A'} | Ruolo: {profile.current_role or 'N/A'}")
        lines.append(
            f"Seniority: {profile.seniority_bucket} | Anni esperienza: "
            f"{profile.years_experience_estimate if profile.years_experience_estimate is not None else 'N/A'}"
        )
        lines.append(
            f"Match Score: {profile.match_score:.2f} | Copertura: {profile.match_ratio:.0%}"
        )
        lines.append("")
        lines.append(
            f"▸ SKILL MATCHATE ({len(profile.matched_skills)}): "
            f"{', '.join(profile.matched_skills) or 'N/A'}"
        )
        lines.append(
            f"▸ SKILL MANCANTI ({len(profile.missing_skills)}): "
            f"{', '.join(profile.missing_skills) or 'N/A'}"
        )
        lines.append(f"▸ TUTTE LE SKILL ({profile.total_skills}):")
        lines.extend(self._serialize_skills(profile.skills))
        lines.append("")
        lines.extend(self._serialize_availability(profile))
        lines.append("")
        lines.extend(self._serialize_reskilling(profile))
        lines.append("")
        lines.extend(self._serialize_experiences(profile))
        lines.append("")
        lines.extend(self._serialize_chunks(profile))
        lines.append("═══════════════════════════")
        return "\n".join(lines)

    def serialize_batch(self, profiles: list[KnowledgeProfile], scenario: str) -> str:
        """Serialize a batch of profiles for the matching scenario.

        Args:
            profiles: KnowledgeProfile list to serialize.
            scenario: Scenario name (only "matching" supported).

        Returns:
            Serialized batch text.
        """
        if scenario != "matching":
            raise ValueError("Only 'matching' scenario is supported for now")
        sections = [
            self.serialize(profile, index=index, total=len(profiles))
            for index, profile in enumerate(profiles, start=1)
        ]
        return "\n\n".join(sections)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token usage for a given text.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

    def _serialize_skills(self, skills: list[SkillDetail]) -> list[str]:
        grouped = self._group_skills_by_domain(skills)
        lines: list[str] = []
        for domain in sorted(grouped):
            items = grouped[domain][: self._max_skills_per_domain]
            formatted = ", ".join(self._format_skill(skill) for skill in items)
            lines.append(f"  [{domain}] {formatted}" if formatted else f"  [{domain}] N/A")
        if not lines:
            return ["  N/A"]
        return lines

    def _serialize_availability(self, profile: KnowledgeProfile) -> list[str]:
        if profile.availability is None:
            return ["▸ DISPONIBILITÀ: N/A"]
        availability = profile.availability
        lines = [
            f"▸ DISPONIBILITÀ: {availability.status} | Allocazione: {availability.allocation_pct}%",
            f"  Progetto: {availability.current_project or 'N/A'}",
            f"  Disponibile: {availability.available_from or 'N/A'} → "
            f"{availability.available_to or 'N/A'}",
            f"  Manager: {availability.manager_name or 'N/A'}",
            f"  IC: {availability.is_intercontratto} "
            f"({profile.ic_sub_state.value if profile.ic_sub_state else 'N/A'})",
        ]
        return lines

    def _serialize_reskilling(self, profile: KnowledgeProfile) -> list[str]:
        if not profile.reskilling_paths:
            return ["▸ RESKILLING ATTIVO:", "  N/A"]
        lines = ["▸ RESKILLING ATTIVO:"]
        for path in profile.reskilling_paths:
            targets = ", ".join(path.target_skills) or "N/A"
            end_date = path.end_date or "N/A"
            lines.append(
                f"  - {path.course_name} ({path.completion_pct}%, "
                f"{path.provider or 'N/A'}, scade {end_date})"
            )
            lines.append(f"    Target: {targets}")
        return lines

    def _serialize_experiences(self, profile: KnowledgeProfile) -> list[str]:
        lines = ["▸ ESPERIENZE RILEVANTI:"]
        if not profile.experiences:
            lines.append("  N/A")
            return lines
        for index, experience in enumerate(profile.experiences[: self._max_experiences], start=1):
            lines.append(
                f"  {index}. [{experience.period}] "
                f"{experience.role or 'N/A'} @ {experience.company or 'N/A'}"
            )
            summary = experience.description_summary or "N/A"
            lines.append(f'     "{summary}"')
            skills = ", ".join(experience.related_skills) or "N/A"
            lines.append(f"     Skills: {skills}")
        return lines

    def _serialize_chunks(self, profile: KnowledgeProfile) -> list[str]:
        lines = ["▸ CHUNK CONTESTUALI (se presenti):"]
        if not profile.relevant_chunks:
            lines.append("  N/A")
            return lines
        for chunk in profile.relevant_chunks[: self._max_chunks]:
            text = chunk.text.strip()
            if len(text) > self._max_chunk_chars:
                text = f"{text[: self._max_chunk_chars].rstrip()}..."
            lines.append(f'  [similarity: {chunk.similarity_score:.2f}] "{text}"')
        return lines

    @staticmethod
    def _group_skills_by_domain(skills: list[SkillDetail]) -> dict[str, list[SkillDetail]]:
        grouped: dict[str, list[SkillDetail]] = {}
        for skill in skills:
            grouped.setdefault(skill.domain, []).append(skill)
        return grouped

    @staticmethod
    def _format_skill(skill: SkillDetail) -> str:
        if skill.source == "reskilling":
            pct = skill.reskilling_completion_pct or 0
            return f"{skill.canonical} (reskilling, {pct}%)"
        return f"{skill.canonical} (cv, {skill.confidence:.2f})"


__all__ = ["KPContextSerializer", "KPContextSerializerConfig"]
