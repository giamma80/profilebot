"""API v1 router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.availability import router as availability_router
from src.api.v1.embeddings import router as embeddings_router
from src.api.v1.search import router as search_router

router = APIRouter()
router.include_router(embeddings_router)
router.include_router(search_router)
router.include_router(availability_router)
