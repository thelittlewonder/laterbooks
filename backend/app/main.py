"""laterbooks FastAPI application."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="laterbooks", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    from app.ocr.detector import _vision_auth_mode

    return {"status": "ok", "vision_auth": _vision_auth_mode()}


@app.get("/health/vision")
async def health_vision() -> dict[str, str | bool]:
    from app.ocr.detector import diagnose_vision

    return diagnose_vision()
