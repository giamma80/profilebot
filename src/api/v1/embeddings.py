"""API endpoints for embedding job queue management."""

from __future__ import annotations

import logging
from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.embedding.celery_app import celery_app
from src.services.embedding.tasks import embed_all_task, embed_batch_task, embed_cv_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/embeddings", tags=["embeddings"])


class EmbeddingItem(BaseModel):
    """Input item for embedding jobs."""

    cv_path: str = Field(..., min_length=1)
    res_id: str = Field(..., min_length=1)


class TriggerSingleRequest(BaseModel):
    """Request payload for single CV embedding."""

    cv_path: str = Field(..., min_length=1)
    dictionary_path: str | None = None
    dry_run: bool = False


class TriggerBatchRequest(BaseModel):
    """Request payload for batch CV embedding."""

    items: list[EmbeddingItem] = Field(..., min_length=1)
    dictionary_path: str | None = None
    dry_run: bool = False


class TriggerAllRequest(BaseModel):
    """Request payload for full embedding run."""

    items: list[EmbeddingItem] = Field(..., min_length=1)
    batch_size: int = Field(default=500, ge=1)
    dictionary_path: str | None = None
    dry_run: bool = False
    force: bool = False


class TaskStatusResponse(BaseModel):
    """Task status response."""

    task_id: str
    status: str
    percentage: int = Field(default=0, ge=0, le=100)
    res_id: str | None = None
    result: dict[str, Any] | None = None
    traceback: str | None = None


class TaskTriggerResponse(BaseModel):
    """Task trigger response."""

    task_id: str
    status: str
    message: str | None = None


def _extract_percentage(result: AsyncResult) -> int:
    info = result.info
    if isinstance(info, dict):
        percentage = info.get("percentage")
        if isinstance(percentage, int):
            return max(0, min(100, percentage))
    if result.successful():
        return 100
    return 0


def _extract_res_id(result: AsyncResult) -> str | None:
    info = result.info
    if isinstance(info, dict):
        res_id = info.get("res_id")
        if isinstance(res_id, str) and res_id:
            return res_id
    if result.successful() and isinstance(result.result, dict):
        res_id = result.result.get("res_id")
        if isinstance(res_id, str) and res_id:
            return res_id
    return None


@router.post(
    "/trigger",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Avvia embedding di tutti i CV",
)
async def trigger_full_embed(request: TriggerAllRequest) -> TaskTriggerResponse:
    """Queue a full embedding job."""
    if not request.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one item is required",
        )

    payload = [item.model_dump() for item in request.items]
    task = embed_all_task.delay(
        items=payload,
        batch_size=request.batch_size,
        dictionary_path=request.dictionary_path,
        dry_run=request.dry_run,
        force=request.force,
    )
    logger.info("Queued full embedding task: %s", task.id)
    return TaskTriggerResponse(
        task_id=task.id,
        status="queued",
        message="Full embedding job started",
    )


@router.post(
    "/trigger/batch",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Avvia embedding batch di CV",
)
async def trigger_batch_embed(request: TriggerBatchRequest) -> TaskTriggerResponse:
    """Queue a batch embedding job."""
    if not request.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one item is required",
        )

    payload = [item.model_dump() for item in request.items]
    task = embed_batch_task.delay(
        items=payload,
        dictionary_path=request.dictionary_path,
        dry_run=request.dry_run,
    )
    logger.info("Queued batch embedding task: %s", task.id)
    return TaskTriggerResponse(
        task_id=task.id,
        status="queued",
        message="Batch embedding job started",
    )


@router.post(
    "/trigger/{res_id}",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Avvia embedding singolo CV",
)
async def trigger_single_embed(
    res_id: str,
    request: TriggerSingleRequest,
) -> TaskTriggerResponse:
    """Queue a single CV embedding job."""
    if not request.cv_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cv_path is required",
        )

    task = embed_cv_task.delay(
        cv_path=request.cv_path,
        res_id=res_id,
        dictionary_path=request.dictionary_path,
        dry_run=request.dry_run,
    )
    logger.info("Queued single embedding task %s for res_id %s", task.id, res_id)
    return TaskTriggerResponse(
        task_id=task.id,
        status="queued",
        message="Single embedding job started",
    )


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Stato del task di embedding",
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Return the status of a queued embedding task."""
    result = AsyncResult(task_id, app=celery_app)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        percentage=_extract_percentage(result),
        res_id=_extract_res_id(result),
        result=result.result if result.ready() else None,
        traceback=result.traceback if result.failed() else None,
    )


@router.get(
    "/stats",
    status_code=status.HTTP_200_OK,
    summary="Statistiche della coda di embedding",
)
async def get_embedding_stats() -> dict[str, Any]:
    """Return Celery queue stats."""
    inspect = celery_app.control.inspect()
    return {
        "active": inspect.active(),
        "reserved": inspect.reserved(),
        "scheduled": inspect.scheduled(),
    }
