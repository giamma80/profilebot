"""Skill extraction pipeline and CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterable
from pathlib import Path

from src.core.parser.schemas import ParsedCV
from src.core.skills.dictionary import SkillDictionary, load_skill_dictionary
from src.core.skills.normalizer import SkillNormalizer
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult

logger = logging.getLogger(__name__)


class SkillExtractor:
    """Extract and normalize skills from parsed CV data."""

    def __init__(self, dictionary: SkillDictionary) -> None:
        """Inizializza l'estrattore con un dizionario skill.

        Args:
            dictionary: Dizionario skill caricato e validato.
        """
        self._dictionary = dictionary
        self._normalizer = SkillNormalizer(dictionary)

    def extract(self, parsed_cv: ParsedCV) -> SkillExtractionResult:
        """Estrae skill normalizzate da un ParsedCV.

        Args:
            parsed_cv: CV già parsato con metadata e sezioni.

        Returns:
            Risultato con skill normalizzate, sconosciute e versione dizionario.
        """
        raw_skills = self._extract_raw_skills(parsed_cv)
        return self.extract_from_raw(cv_id=parsed_cv.metadata.cv_id, raw_skills=raw_skills)

    def extract_from_raw(
        self,
        cv_id: str,
        raw_skills: Iterable[str],
    ) -> SkillExtractionResult:
        """Estrae skill normalizzate da input raw.

        Args:
            cv_id: Identificativo del CV in elaborazione.
            raw_skills: Lista/iterabile di skill grezze.

        Returns:
            Risultato con skill normalizzate, sconosciute e versione dizionario.
        """
        normalized: list[NormalizedSkill] = []
        unknown: list[str] = []

        for raw in raw_skills:
            cleaned = self._clean(raw)
            if not cleaned:
                continue

            normalized_skill = self._normalizer.normalize(raw)
            if normalized_skill is None:
                unknown.append(cleaned)
                logger.warning("Unknown skill: '%s' from CV '%s'", cleaned, cv_id)
            else:
                normalized.append(normalized_skill)

        return SkillExtractionResult(
            cv_id=cv_id,
            normalized_skills=normalized,
            unknown_skills=unknown,
            dictionary_version=self._dictionary.version,
        )

    def extract_from_parsed_cv(self, parsed_cv: ParsedCV) -> SkillExtractionResult:
        """Estrae skill normalizzate da un ParsedCV.

        Args:
            parsed_cv: CV già parsato con metadata e sezioni.

        Returns:
            Risultato con skill normalizzate, sconosciute e versione dizionario.
        """
        return self.extract(parsed_cv)

    def _extract_raw_skills(self, parsed_cv: ParsedCV) -> list[str]:
        """Collect raw skills from ParsedCV with fallbacks."""
        if parsed_cv.skills and parsed_cv.skills.skill_keywords:
            return parsed_cv.skills.skill_keywords
        if parsed_cv.skills and parsed_cv.skills.raw_text:
            return _split_text_to_skills(parsed_cv.skills.raw_text)
        return _split_text_to_skills(parsed_cv.raw_text)

    @staticmethod
    def _clean(text: str) -> str:
        """Normalize and trim raw skill text."""
        return text.strip().lower()


def _split_text_to_skills(text: str) -> list[str]:
    """Split a text blob into potential skills."""
    if not text:
        return []

    tokens: list[str] = []
    normalized = text.replace("\n", ",").replace("\r", ",").replace(";", ",").replace("|", ",")
    for chunk in normalized.split(","):
        cleaned = chunk.strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize skills from raw text or a file.",
    )
    parser.add_argument(
        "--text",
        type=str,
        help='Comma-separated skills string (e.g., "Python, FastAPI, SQL")',
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to a text file containing skills (comma-separated or line-based).",
    )
    parser.add_argument(
        "--cv-id",
        type=str,
        default="cv_cli",
        help="CV identifier for logging purposes.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("data/skills_dictionary.yaml"),
        help="Path to the skills dictionary YAML.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def _load_skills_from_file(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) == 1:
        return _split_text_to_skills(lines[0])
    skills: list[str] = []
    for line in lines:
        skills.extend(_split_text_to_skills(line))
    return skills


def main() -> int:
    """CLI entrypoint for skill extraction."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    if not args.text and not args.file:
        print("Provide --text or --file")
        return 1

    if args.text:
        raw_skills = _split_text_to_skills(args.text)
    else:
        raw_skills = _load_skills_from_file(args.file)

    dictionary = load_skill_dictionary(args.dictionary)
    extractor = SkillExtractor(dictionary)

    result = extractor.extract_from_raw(cv_id=args.cv_id, raw_skills=raw_skills)
    payload = result.model_dump()
    payload["stats"] = result.get_stats()

    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
