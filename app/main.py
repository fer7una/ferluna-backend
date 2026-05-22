from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from app.data import CV, DOCS, POSTS, PROFILE, PROJECTS, site_payload

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


def resolve_route(path: str) -> tuple[int, dict[str, Any]]:
    route = urlparse(path).path.rstrip("/") or "/"

    routes: dict[str, dict[str, Any]] = {
        "/api/health": {"status": "ok", "service": "ferluna-backend"},
        "/api/profile": PROFILE,
        "/api/cv": CV,
        "/api/projects": {"projects": PROJECTS},
        "/api/posts": {"posts": POSTS},
        "/api/docs": {"docs": DOCS},
        "/api/site": site_payload(),
    }

    if route in routes:
        return HTTPStatus.OK, routes[route]

    return HTTPStatus.NOT_FOUND, {
        "error": "not_found",
        "message": f"No route registered for {route}",
    }


class FernandoLunaHandler(BaseHTTPRequestHandler):
    server_version = "FernandoLunaAPI/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        status, payload = resolve_route(self.path)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        self.send_header("Access-Control-Allow-Origin", cors_origin(origin))
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")

    def log_message(self, format: str, *args: object) -> None:
        if os.environ.get("FERLUNA_API_LOGS", "1") != "0":
            super().log_message(format, *args)


def run() -> None:
    host = os.environ.get("FERLUNA_API_HOST", "127.0.0.1")
    port = int(os.environ.get("FERLUNA_API_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), FernandoLunaHandler)
    print(f"Fernando Luna API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
