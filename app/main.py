from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from app.env_loader import load_env_file

load_env_file()

from app.application.auth.rate_limit import reset_login_attempts
from app.application.content.site_service import initialize_database, seed_database
from app.interfaces.http.cors import cors_origin
from app.interfaces.http.errors import with_runtime_errors, with_value_errors
from app.interfaces.http.routes import (
    authorize_admin,
    resolve_admin_login,
    resolve_admin_route,
    resolve_route,
)

MAX_JSON_BODY_BYTES = 256 * 1024


class FernandoLunaHandler(BaseHTTPRequestHandler):
    server_version = "FernandoLunaAPI/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def client_id(self) -> str | None:
        address = getattr(self, "client_address", None)
        if isinstance(address, tuple) and address:
            return str(address[0])
        return None

    def do_GET(self) -> None:
        if urlparse(self.path).path.rstrip("/") in {"/api/admin/site", "/api/admin/login"}:
            status, payload = resolve_admin_route(
                self.path, "GET", self.headers, client_id=self.client_id()
            )
        else:
            status, payload = resolve_route(self.path)

        self.send_json(status, payload)

    def do_POST(self) -> None:
        self.handle_write_request("POST")

    def do_PUT(self) -> None:
        self.handle_write_request("PUT")

    def handle_write_request(self, method: str) -> None:
        body = self.read_json_body()
        if isinstance(body, tuple):
            status, payload = body
        else:
            status, payload = resolve_admin_route(
                self.path, method, self.headers, body, client_id=self.client_id()
            )

        self.send_json(status, payload)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except ConnectionError:
            return

    def read_json_body(self) -> dict[str, Any] | tuple[int, dict[str, Any]]:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "0")
        except ValueError:
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_content_length",
                "message": "Content-Length must be an integer",
            }

        if length <= 0:
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_json",
                "message": "JSON body is required",
            }

        if length > MAX_JSON_BODY_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                "error": "payload_too_large",
                "message": f"Request body exceeds {MAX_JSON_BODY_BYTES} bytes",
            }

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_json",
                "message": "Request body must be valid JSON",
            }

        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_json",
                "message": "Request body must be a JSON object",
            }

        return payload

    def send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        self.send_header("Access-Control-Allow-Origin", cors_origin(origin))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Vary", "Origin")

    def log_message(self, format: str, *args: object) -> None:
        if os.environ.get("FERLUNA_API_LOGS", "1") != "0":
            super().log_message(format, *args)


def run() -> None:
    if len(sys.argv) > 1:
        run_cli(sys.argv[1])
        return

    host = os.environ.get("FERLUNA_API_HOST", "127.0.0.1")
    port = int(os.environ.get("FERLUNA_API_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), FernandoLunaHandler)
    print(f"Fernando Luna API listening on http://{host}:{port}")
    server.serve_forever()


def run_cli(command: str) -> None:
    if command == "init-db":
        initialize_database()
        print("Database schema initialized")
        return

    if command == "seed-db":
        seed_database()
        print("Database seeded with default content")
        return

    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    run()
