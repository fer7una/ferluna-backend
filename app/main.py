from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from app.auth import (
    AuthConfigError,
    TokenValidationError,
    create_admin_jwt,
    is_admin_auth_configured,
    validate_admin_authorization,
    verify_admin_password,
)
from app.content_store import (
    DatabaseDependencyError,
    DatabaseDisabledError,
    initialize_database,
    load_admin_site_payload,
    public_site_payload,
    replace_admin_site_payload,
    seed_database,
)
from app.data import CV, DOCS, POSTS, PROFILE, PROJECTS

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
MAX_JSON_BODY_BYTES = 256 * 1024


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
    }

    if route in routes:
        return HTTPStatus.OK, routes[route]

    if route == "/api/site":
        return with_runtime_errors(public_site_payload)

    return HTTPStatus.NOT_FOUND, {
        "error": "not_found",
        "message": f"No route registered for {route}",
    }


def resolve_admin_route(
    path: str,
    method: str,
    headers: Any,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    route = urlparse(path).path.rstrip("/") or "/"
    if route == "/api/admin/login":
        if method != "POST":
            return HTTPStatus.METHOD_NOT_ALLOWED, {
                "error": "method_not_allowed",
                "message": f"{method} is not allowed for {route}",
            }
        if body is None:
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_json",
                "message": "JSON body is required",
            }
        return resolve_admin_login(body)

    if route != "/api/admin/site":
        return HTTPStatus.NOT_FOUND, {
            "error": "not_found",
            "message": f"No admin route registered for {route}",
        }

    auth_status = authorize_admin(headers.get("Authorization"))
    if auth_status is not None:
        return auth_status

    if method == "GET":
        return with_runtime_errors(load_admin_site_payload)

    if method in {"POST", "PUT"}:
        if body is None:
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_json",
                "message": "JSON body is required",
            }
        return with_value_errors(lambda: replace_admin_site_payload(body))

    return HTTPStatus.METHOD_NOT_ALLOWED, {
        "error": "method_not_allowed",
        "message": f"{method} is not allowed for {route}",
    }


def resolve_admin_login(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    password = body.get("password")
    if not isinstance(password, str) or not password:
        return HTTPStatus.BAD_REQUEST, {
            "error": "invalid_payload",
            "message": "password is required",
        }

    try:
        if not is_admin_auth_configured():
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": "admin_disabled",
                "message": "FERLUNA_ADMIN_PASSWORD and FERLUNA_JWT_SECRET must be configured",
            }
        if not verify_admin_password(password):
            return HTTPStatus.UNAUTHORIZED, {
                "error": "unauthorized",
                "message": "Invalid admin credentials",
            }
        return HTTPStatus.OK, create_admin_jwt()
    except AuthConfigError as error:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "error": "admin_disabled",
            "message": str(error),
        }


def authorize_admin(authorization: str | None) -> tuple[int, dict[str, Any]] | None:
    try:
        validate_admin_authorization(authorization)
    except AuthConfigError as error:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "error": "admin_disabled",
            "message": str(error),
        }
    except TokenValidationError as error:
        return HTTPStatus.UNAUTHORIZED, {
            "error": "unauthorized",
            "message": str(error),
        }

    return None


def with_runtime_errors(factory: Any) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, factory()
    except DatabaseDisabledError as error:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "error": "database_disabled",
            "message": str(error),
        }
    except DatabaseDependencyError as error:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "error": "database_dependency_missing",
            "message": str(error),
        }
    except Exception:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {
            "error": "internal_error",
            "message": "Unexpected server error",
        }


def with_value_errors(factory: Any) -> tuple[int, dict[str, Any]]:
    try:
        return HTTPStatus.OK, factory()
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {
            "error": "invalid_payload",
            "message": str(error),
        }
    except DatabaseDisabledError as error:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "error": "database_disabled",
            "message": str(error),
        }
    except DatabaseDependencyError as error:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "error": "database_dependency_missing",
            "message": str(error),
        }
    except Exception:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {
            "error": "internal_error",
            "message": "Unexpected server error",
        }


class FernandoLunaHandler(BaseHTTPRequestHandler):
    server_version = "FernandoLunaAPI/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if urlparse(self.path).path.rstrip("/") in {"/api/admin/site", "/api/admin/login"}:
            status, payload = resolve_admin_route(self.path, "GET", self.headers)
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
            status, payload = resolve_admin_route(self.path, method, self.headers, body)

        self.send_json(status, payload)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

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
