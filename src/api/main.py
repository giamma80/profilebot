"""FastAPI application entrypoint for ProfileBot."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.v1.router import router as v1_router
from src.services.qdrant import check_qdrant_health, get_qdrant_client

load_dotenv()

app = FastAPI(
    title="ProfileBot API",
    version="0.1.0",
    description="API per gestione embedding e servizi di salute applicativa.",
    contact={"name": "ProfileBot Team", "email": "team@profilebot.local"},
    servers=[{"url": "/", "description": "Default"}],
    openapi_tags=[
        {
            "name": "embeddings",
            "description": "Gestione dei job di embedding.",
        },
        {
            "name": "search",
            "description": "Ricerca profili per skill.",
        },
        {
            "name": "availability",
            "description": "Gestione disponibilità e cache.",
        },
        {
            "name": "health",
            "description": "Verifiche di stato e disponibilità.",
        },
    ],
)

app.include_router(v1_router)


@app.get("/health", tags=["health"])
def health_check() -> JSONResponse:
    """Return application and Qdrant health status."""
    client = get_qdrant_client()
    try:
        qdrant_status = check_qdrant_health(client)
        status = "ok"
    except Exception as exc:  # pylint: disable=broad-exception-caught  # pragma: no cover
        qdrant_status = {"status": "down", "error": str(exc)}
        status = "degraded"

    return JSONResponse(
        {
            "status": status,
            "qdrant": qdrant_status,
        }
    )
