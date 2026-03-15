"""Skill extraction pipeline and CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections.abc import Iterable
from pathlib import Path

from src.core.parser.schemas import ParsedCV
from src.core.skills.blacklist import SkillBlacklist, load_skill_blacklist
from src.core.skills.dictionary import SkillDictionary, load_skill_dictionary
from src.core.skills.normalizer import SkillNormalizer
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult

logger = logging.getLogger(__name__)

MIN_SENTENCE_WORDS = 8
SENTENCE_LENGTH_THRESHOLD = 80
BULLET_PREFIX_PATTERN = "^[•\\-\\u2013\\u2014]\\s*"


class SkillExtractor:
    """Extract and normalize skills from parsed CV data."""

    def __init__(
        self,
        dictionary: SkillDictionary,
        blacklist: SkillBlacklist | None = None,
    ) -> None:
        """Inizializza l'estrattore con un dizionario skill.

        Args:
            dictionary: Dizionario skill caricato e validato.
            blacklist: Blacklist opzionale per filtrare token non-skill.
        """
        self._dictionary = dictionary
        self._blacklist = blacklist or load_skill_blacklist()
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
            for token in _split_text_to_skills(raw):
                cleaned = self._clean(token)
                if not cleaned:
                    continue
                if self._blacklist.is_blocked(cleaned):
                    continue

                normalized_skill = self._normalizer.normalize(token)
                if normalized_skill is None:
                    candidates = self._expand_candidates(token)
                    matched = False
                    for candidate in candidates:
                        candidate_clean = self._clean(candidate)
                        if not candidate_clean:
                            continue
                        if self._blacklist.is_blocked(candidate_clean):
                            continue
                        normalized_candidate = self._normalizer.normalize(candidate)
                        if normalized_candidate is None:
                            continue
                        normalized.append(normalized_candidate)
                        matched = True
                    if not matched:
                        if self._is_sentence_like(cleaned):
                            continue
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
        return []

    @staticmethod
    def _clean(text: str) -> str:
        """Normalize and trim raw skill text."""
        return text.strip().lower()

    @staticmethod
    def _is_sentence_like(text: str) -> bool:
        words = text.split()
        if len(words) < MIN_SENTENCE_WORDS:
            return False
        lowered = text.lower()
        markers = (
            "sono ",
            "ho ",
            "mi ",
            "credo",
            "definisco",
            "ritengo",
            "persona",
            "capace",
            "generalmente",
            "posso",
        )
        if any(marker in lowered for marker in markers):
            return True
        if "." in text or ";" in text:
            return True
        return len(text) >= SENTENCE_LENGTH_THRESHOLD

    @staticmethod
    def _expand_candidates(text: str) -> list[str]:
        cleaned = re.sub(BULLET_PREFIX_PATTERN, "", text).replace("\t", " ").strip()
        if not cleaned:
            return []
        cleaned = cleaned.replace("(", ",").replace(")", ",")
        cleaned = re.sub(r"\\s+", " ", cleaned)
        parts = re.split(r"[,/;|]", cleaned)

        candidates: list[str] = []
        seen: set[str] = set()
        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue
            cleaned_part = SkillExtractor._strip_prefixes(stripped)
            subparts = re.split(r"\\s+(?:e|ed|con|tramite|in|per|su)\\s+", cleaned_part)
            for sub in subparts:
                token = sub.strip().strip(".:")
                if not token or token in seen:
                    continue
                seen.add(token)
                candidates.append(token)
        return candidates

    @staticmethod
    def _strip_prefixes(text: str) -> str:
        prefixes = (
            r"esperienza\\s+con",
            r"utilizzo\\s+di",
            r"uso\\s+di",
            r"implementazione\\s+di",
            r"sviluppo\\s+(?:backend|frontend)?\\s*(?:in|con)?",
            r"testing\\s+automatico\\s+in",
            r"ottimizzazione\\s+(?:delle|dei|del)?",
            r"interrogazioni\\s+",
            r"gestione\\s+di",
            r"struttura\\s+e\\s+gestione",
            r"database\\s+e\\s+gestione\\s+dati",
            r"protocolli\\s+di\\s+comunicazione\\s+e\\s+integrazioni",
            r"frontend\\s+e\\s+ui/ux",
        )
        for prefix in prefixes:
            text = re.sub(rf"^(?:{prefix})\\s+", "", text, flags=re.IGNORECASE)
        return text.strip()


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
