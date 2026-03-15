"""API v1 router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.availability import router as availability_router
from src.api.v1.embeddings import router as embeddings_router
from src.api.v1.ingestion import router as ingestion_router
from src.api.v1.job_match import router as job_match_router
from src.api.v1.metrics import router as metrics_router
from src.api.v1.search import router as search_router

router = APIRouter()
router.include_router(embeddings_router)
router.include_router(ingestion_router)
router.include_router(search_router)
router.include_router(availability_router)
router.include_router(job_match_router)
router.include_router(metrics_router)
