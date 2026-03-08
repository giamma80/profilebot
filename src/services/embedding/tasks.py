"""Celery tasks for embedding jobs."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.parser import parse_docx, parse_docx_bytes
from src.core.skills import SkillExtractor, load_skill_dictionary
from src.services.embedding.celery_app import celery_app
from src.services.scraper.cache import ScraperResIdCache
from src.services.scraper.client import ScraperClient
from src.services.scraper.tasks import _ensure_scraper_base_url

logger = logging.getLogger(__name__)

DEFAULT_DICTIONARY_PATH = "data/skills_dictionary.yaml"


def _resolve_dictionary_path(dictionary_path: str | None) -> Path:
    env_path = os.getenv("SKILLS_DICTIONARY_PATH")
    raw_path = dictionary_path or env_path or DEFAULT_DICTIONARY_PATH
    return Path(raw_path)


def _embed_cv(
    cv_path: Path,
    dictionary_path: str | None,
    dry_run: bool,
    *,
    extractor: SkillExtractor | None = None,
    pipeline: EmbeddingPipeline | None = None,
) -> tuple[str, int, dict[str, int]]:
    extractor_instance = extractor or SkillExtractor(
        load_skill_dictionary(_resolve_dictionary_path(dictionary_path))
    )

    parsed_cv = parse_docx(cv_path)
    skill_result = extractor_instance.extract(parsed_cv)

    pipeline_instance = pipeline or EmbeddingPipeline()
    result = pipeline_instance.process_cv(parsed_cv, skill_result, dry_run=dry_run)
    return parsed_cv.metadata.cv_id, parsed_cv.metadata.res_id, result


def _chunked(
    items: list[dict[str, Any]],
    batch_size: int,
) -> Iterable[list[dict[str, Any]]]:
    if batch_size <= 0:
        return
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


@celery_app.task(bind=True, max_retries=3, name="embedding.index_cv")
def embed_cv_task(
    self,
    cv_path: str,
    *,
    res_id: str | None = None,
    dictionary_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Embed a single CV and index it into Qdrant.

    Args:
        cv_path: Path to the CV document (.docx).
        res_id: Unique profile identifier (matricola aziendale).
        dictionary_path: Optional path to the skills dictionary.
        dry_run: When True, compute embeddings without writing to Qdrant.

    Returns:
        Task result summary with indexing counts.
    """
    try:
        path = Path(cv_path)
        if not path.exists():
            raise FileNotFoundError(f"CV file not found: {path}")
        if path.suffix.lower() != ".docx":
            logger.warning("CV file extension is not .docx: %s", path)

        if self.request.id is not None:
            self.update_state(state="PROGRESS", meta={"percentage": 10, "res_id": res_id})
        cv_id, parsed_res_id, result = _embed_cv(path, dictionary_path, dry_run)
        if res_id and str(res_id) != str(parsed_res_id):
            logger.warning("res_id mismatch for CV '%s': '%s'", cv_id, res_id)
        if self.request.id is not None:
            self.update_state(
                state="PROGRESS",
                meta={"percentage": 100, "cv_id": cv_id, "res_id": parsed_res_id},
            )

        return {
            "status": "success",
            "cv_id": cv_id,
            "res_id": parsed_res_id,
            "result": result,
            "dry_run": dry_run,
            "percentage": 100,
        }
    except Exception as exc:
        logger.exception("Failed embedding CV: %s", cv_path)
        raise self.retry(exc=exc, countdown=60) from exc


@celery_app.task(bind=True, name="embedding.index_cv_batch")
def embed_batch_task(
    self,
    items: list[dict[str, Any]],
    *,
    dictionary_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Embed a batch of CVs within the same task.

    Args:
        items: List of dicts with at least ``cv_path`` and optional ``res_id``.
        dictionary_path: Optional path to the skills dictionary.
        dry_run: When True, compute embeddings without writing to Qdrant.

    Returns:
        Summary with processed counts and totals.
    """
    if not items:
        return {"status": "empty", "processed": 0, "failed": 0, "totals": {}}

    processed = 0
    failed = 0
    totals = {"cv_skills": 0, "cv_experiences": 0, "total": 0}
    errors: list[dict[str, str]] = []

    total_items = len(items)
    dictionary = load_skill_dictionary(_resolve_dictionary_path(dictionary_path))
    extractor = SkillExtractor(dictionary)
    pipeline = EmbeddingPipeline()
    for index, item in enumerate(items, start=1):
        cv_path = item.get("cv_path")
        res_id = item.get("res_id")
        if not cv_path:
            failed += 1
            errors.append({"file": "", "error": "Missing cv_path"})
            continue

        try:
            path = Path(cv_path)
            if not path.exists():
                raise FileNotFoundError(f"CV file not found: {path}")
            if path.suffix.lower() != ".docx":
                logger.warning("CV file extension is not .docx: %s", path)

            cv_id, parsed_res_id, result = _embed_cv(
                path,
                dictionary_path,
                dry_run,
                extractor=extractor,
                pipeline=pipeline,
            )
            if res_id and str(res_id) != str(parsed_res_id):
                logger.warning("res_id mismatch for CV '%s': '%s'", cv_id, res_id)
            totals["cv_skills"] += result.get("cv_skills", 0)
            totals["cv_experiences"] += result.get("cv_experiences", 0)
            totals["total"] += result.get("total", 0)
            processed += 1

            percentage = int(index / total_items * 100)
            self.update_state(
                state="PROGRESS",
                meta={"percentage": percentage, "cv_id": cv_id, "res_id": parsed_res_id},
            )
        except Exception as exc:
            failed += 1
            logger.exception("Failed embedding CV in batch: %s", cv_path)
            errors.append({"file": str(cv_path), "error": str(exc)})

    return {
        "status": "completed",
        "processed": processed,
        "failed": failed,
        "totals": totals,
        "errors": errors,
        "percentage": 100,
    }


@celery_app.task(bind=True, name="embedding.index_all_cvs")
def embed_all_task(  # noqa: PLR0913 - task signature mirrors API payload
    self,
    items: list[dict[str, Any]],
    *,
    batch_size: int = 500,
    dictionary_path: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Embed all CVs by processing batches sequentially in a single task.

    Args:
        items: List of dicts with at least ``cv_path`` and optional ``res_id``.
        batch_size: Number of items per batch.
        dictionary_path: Optional path to the skills dictionary.
        dry_run: When True, compute embeddings without writing to Qdrant.
        force: Reserved for future use.

    Returns:
        Summary with processed counts and totals.
    """
    if not items:
        return {"status": "empty", "processed": 0, "failed": 0, "totals": {}}

    processed = 0
    failed = 0
    totals = {"cv_skills": 0, "cv_experiences": 0, "total": 0}
    errors: list[dict[str, str]] = []

    total_items = len(items)
    if batch_size <= 0:
        batch_size = total_items or 1

    dictionary = load_skill_dictionary(_resolve_dictionary_path(dictionary_path))
    extractor = SkillExtractor(dictionary)
    pipeline = EmbeddingPipeline()

    processed_so_far = 0
    for batch in _chunked(items, batch_size):
        for item in batch:
            cv_path = item.get("cv_path")
            res_id = item.get("res_id")
            parsed_res_id = res_id
            if not cv_path:
                failed += 1
                errors.append({"file": "", "error": "Missing cv_path"})
                processed_so_far += 1
                continue

            try:
                path = Path(cv_path)
                if not path.exists():
                    raise FileNotFoundError(f"CV file not found: {path}")
                if path.suffix.lower() != ".docx":
                    logger.warning("CV file extension is not .docx: %s", path)

                cv_id, parsed_res_id, result = _embed_cv(
                    path,
                    dictionary_path,
                    dry_run,
                    extractor=extractor,
                    pipeline=pipeline,
                )
                if res_id and str(res_id) != str(parsed_res_id):
                    logger.warning("res_id mismatch for CV '%s': '%s'", cv_id, res_id)
                totals["cv_skills"] += result.get("cv_skills", 0)
                totals["cv_experiences"] += result.get("cv_experiences", 0)
                totals["total"] += result.get("total", 0)
                processed += 1
            except Exception as exc:
                failed += 1
                logger.exception("Failed embedding CV in full run: %s", cv_path)
                errors.append({"file": str(cv_path), "error": str(exc)})
            finally:
                processed_so_far += 1
                percentage = int(processed_so_far / total_items * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={"percentage": percentage, "res_id": parsed_res_id},
                )

    return {
        "status": "completed",
        "processed": processed,
        "failed": failed,
        "totals": totals,
        "errors": errors,
        "percentage": 100,
        "force": force,
    }


@celery_app.task(bind=True, name="embedding.index_from_scraper")
def embed_from_scraper_task(
    self,
    _results: list[Any] | None = None,
    _errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Download CVs from the scraper service and index them into Qdrant."""
    if not _ensure_scraper_base_url():
        return {"status": "skipped", "reason": "SCRAPER_BASE_URL not configured"}

    res_ids: list[int] = []
    if _results is not None:
        for item in _results:
            if isinstance(item, dict):
                res_id = item.get("res_id")
                status = item.get("status")
                if isinstance(res_id, int) and (status is None or status == "success"):
                    res_ids.append(res_id)
        if not res_ids:
            return {
                "status": "empty",
                "processed": 0,
                "failed": 0,
                "totals": {"cv_skills": 0, "cv_experiences": 0, "total": 0},
                "errors": [],
                "percentage": 0,
            }
    else:
        cache = ScraperResIdCache()
        res_ids = cache.get_res_ids()
        if not res_ids:
            return {
                "status": "empty",
                "processed": 0,
                "failed": 0,
                "totals": {"cv_skills": 0, "cv_experiences": 0, "total": 0},
                "errors": [],
                "percentage": 0,
            }

    dictionary = load_skill_dictionary(_resolve_dictionary_path(None))
    extractor = SkillExtractor(dictionary)
    pipeline = EmbeddingPipeline()

    processed = 0
    failed = 0
    totals = {"cv_skills": 0, "cv_experiences": 0, "total": 0}
    errors: list[dict[str, int | str]] = []
    total_res_ids = len(res_ids)

    with ScraperClient() as client:
        for index, res_id in enumerate(res_ids, start=1):
            try:
                data = client.download_inside_cv(res_id)
                parsed_cv = parse_docx_bytes(data, res_id)
                skill_result = extractor.extract(parsed_cv)
                result = pipeline.process_cv(parsed_cv, skill_result)
                totals["cv_skills"] += result.get("cv_skills", 0)
                totals["cv_experiences"] += result.get("cv_experiences", 0)
                totals["total"] += result.get("total", 0)
                processed += 1
            except Exception as exc:
                failed += 1
                errors.append({"res_id": res_id, "error": str(exc)})
                logger.exception("Failed embedding CV for res_id %s", res_id)
            finally:
                percentage = int(index / total_res_ids * 100)
                if self.request.id is not None:
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "percentage": percentage,
                            "res_id": res_id,
                            "processed": processed,
                            "failed": failed,
                        },
                    )

    return {
        "status": "completed",
        "processed": processed,
        "failed": failed,
        "totals": totals,
        "errors": errors,
        "percentage": 100,
    }
