"""Chunk point builder for chunk-based indexing."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from qdrant_client import models

from src.core.embedding.service import EmbeddingService
from src.core.parser.schemas import ParsedCV

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_MAX_CHARS = 800
DEFAULT_PREVIEW_MAX_CHARS = 160


@dataclass(frozen=True)
class ChunkCandidate:
    section_type: str
    chunk_index: int
    text: str


def build_chunk_points(
    parsed_cv: ParsedCV,
    embedding_service: EmbeddingService,
    ingested_at: datetime,
) -> list[models.PointStruct]:
    """Build cv_chunks points for chunk-based search.

    Args:
        parsed_cv: Parsed CV object from the parser.
        embedding_service: Embedding service for chunk vectors.
        ingested_at: Ingestion timestamp for chunk payloads.

    Returns:
        List of Qdrant PointStruct for chunk indexing.
    """
    candidates = _collect_chunk_candidates(parsed_cv)
    if not candidates:
        return []

    points: list[models.PointStruct] = []
    for batch in _chunked(candidates, _get_batch_size()):
        texts = [item.text for item in batch]
        vectors = embedding_service.embed_batch(texts)

        if len(vectors) != len(texts):
            logger.warning(
                "Embedding batch size mismatch for CV '%s': %d texts, %d vectors",
                parsed_cv.metadata.cv_id,
                len(texts),
                len(vectors),
            )

        for candidate, vector in zip(batch, vectors, strict=False):
            point_id = _generate_chunk_id(
                parsed_cv.metadata.cv_id,
                candidate.section_type,
                candidate.chunk_index,
            )
            payload = {
                "cv_id": parsed_cv.metadata.cv_id,
                "res_id": parsed_cv.metadata.res_id,
                "section_type": candidate.section_type,
                "chunk_index": candidate.chunk_index,
                "chunk_text": candidate.text,
                "text_preview": _build_text_preview(candidate.text),
                "ingested_at": ingested_at,
            }
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))

    return points


def _collect_chunk_candidates(parsed_cv: ParsedCV) -> list[ChunkCandidate]:
    candidates: list[ChunkCandidate] = []
    sections = [
        ("summary", _build_summary_text(parsed_cv)),
        ("education", _join_lines(parsed_cv.education)),
        ("certifications", _join_lines(parsed_cv.certifications)),
        ("generic", parsed_cv.raw_text),
    ]

    max_chars = _get_chunk_max_chars()
    for section_type, raw_text in sections:
        for index, chunk_text in enumerate(_chunk_text(raw_text, max_chars)):
            candidates.append(
                ChunkCandidate(
                    section_type=section_type,
                    chunk_index=index,
                    text=chunk_text,
                )
            )

    return candidates


def _build_summary_text(parsed_cv: ParsedCV) -> str:
    parts: list[str] = []
    if parsed_cv.metadata.full_name:
        parts.append(parsed_cv.metadata.full_name.strip())
    if parsed_cv.metadata.current_role:
        parts.append(parsed_cv.metadata.current_role.strip())
    if parsed_cv.skills and parsed_cv.skills.raw_text.strip():
        parts.append(parsed_cv.skills.raw_text.strip())
    return "\n".join(part for part in parts if part)


def _chunk_text(text: str, max_chars: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned or max_chars <= 0:
        return []

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return _chunk_by_length(cleaned, max_chars)

    chunks: list[str] = []
    buffer = ""
    for line in lines:
        candidate = f"{buffer}\n{line}" if buffer else line
        if len(candidate) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = line
            else:
                chunks.extend(_chunk_by_length(line, max_chars))
                buffer = ""
        else:
            buffer = candidate

    if buffer:
        chunks.append(buffer)

    return chunks


def _chunk_by_length(text: str, max_chars: int) -> list[str]:
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _chunked(
    items: list[ChunkCandidate],
    batch_size: int,
) -> Iterable[list[ChunkCandidate]]:
    if batch_size <= 0:
        return
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def _build_text_preview(text: str) -> str:
    preview = " ".join(text.split())
    if len(preview) <= DEFAULT_PREVIEW_MAX_CHARS:
        return preview
    return f"{preview[:DEFAULT_PREVIEW_MAX_CHARS].rstrip()}..."


def _get_batch_size() -> int:
    raw = os.getenv("EMBEDDING_BATCH_SIZE", "100")
    try:
        value = int(raw)
    except ValueError:
        value = 100
    return max(1, value)


def _get_chunk_max_chars() -> int:
    raw = os.getenv("CHUNK_MAX_CHARS", str(DEFAULT_CHUNK_MAX_CHARS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_CHUNK_MAX_CHARS
    return max(100, value)


def _generate_chunk_id(cv_id: str, section_type: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{cv_id}:chunk:{section_type}:{chunk_index}"))


def _join_lines(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip())
