import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, dashboard, graph, ingest, onboarding
from app.config import settings
from app.db import falkor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="OnboardOS API",
    description="Evidence-backed company memory, transcript ingestion, and onboarding.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(dashboard.router)
app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(graph.router)
app.include_router(onboarding.router)


@app.get("/health", tags=["health"])
def health():
    graph_available = falkor.ping()
    return {
        "status": "ok" if graph_available else "degraded",
        "database": "connected" if graph_available else "unavailable",
        "gemini_configured": bool(settings.gemini_api_key),
        "demo_mode": settings.demo_mode,
        "graph": settings.falkordb_graph,
    }
