"""FastAPI application entrypoint for ProfileBot."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from src.services.qdrant import check_qdrant_health, get_qdrant_client

load_dotenv()

app = FastAPI(title="ProfileBot API", version="0.1.0")


@app.get("/health")
def health_check() -> JSONResponse:
    """Return application and Qdrant health status."""
    client = get_qdrant_client()
    try:
        qdrant_status = check_qdrant_health(client)
        status = "ok"
    except Exception as exc:  # pragma: no cover - defensive health check
        qdrant_status = {"status": "down", "error": str(exc)}
        status = "degraded"

    return JSONResponse(
        {
            "status": status,
            "qdrant": qdrant_status,
        }
    )
