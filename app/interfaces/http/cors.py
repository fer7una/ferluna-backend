from __future__ import annotations

import os

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def allowed_origins() -> list[str]:
    raw_origins = os.environ.get("FERLUNA_CORS_ORIGINS", DEFAULT_ORIGINS)
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def cors_origin(request_origin: str | None) -> str:
    origins = allowed_origins()
    if "*" in origins:
        return "*"
    if request_origin in origins:
        return request_origin
    return origins[0] if origins else "http://localhost:5173"
