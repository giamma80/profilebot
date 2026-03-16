"""FastAPI application entrypoint for ProfileBot."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.v1.router import router as v1_router
from src.services.qdrant import check_qdrant_health, get_qdrant_client
from src.utils.metrics import get_metrics_registry

load_dotenv()

app = FastAPI(
    title="ProfileBot API",
    version="0.1.0",
    description="API per gestione embedding e servizi di salute applicativa.",
    contact={"name": "ProfileBot Team", "email": "team@profilebot.example.com"},
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
            "name": "ingestion",
            "description": "Ingestion atomica per profilo.",
        },
        {
            "name": "profiles",
            "description": "Dati di profilo e percorsi di reskilling.",
        },
        {
            "name": "health",
            "description": "Verifiche di stato e disponibilità.",
        },
    ],
)

# Initialize Instrumentator without exposing the default /metrics endpoint
# so we can expose our own custom one that includes multiprocess metrics
instrumentator = Instrumentator(
    excluded_handlers=["/metrics"],
    registry=REGISTRY,
).instrument(app)


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Return Prometheus metrics plain text format."""
    custom_registry = get_metrics_registry()
    data = generate_latest(REGISTRY) + generate_latest(custom_registry)
    return Response(data, headers={"Content-Type": CONTENT_TYPE_LATEST})


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
