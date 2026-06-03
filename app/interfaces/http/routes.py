from __future__ import annotations

from http import HTTPStatus
from typing import Any
from urllib.parse import urlparse

from app.application.auth.rate_limit import login_rate_limited, reset_login_attempts
from app.application.content.site_service import (
    load_admin_site_payload,
    public_site_payload,
    replace_admin_site_payload,
)
from app.auth import (
    AuthConfigError,
    TokenValidationError,
    create_admin_jwt,
    is_admin_auth_configured,
    validate_admin_authorization,
    verify_admin_password,
)
from app.interfaces.http.errors import with_runtime_errors, with_value_errors


def resolve_route(path: str) -> tuple[int, dict[str, Any]]:
    route = urlparse(path).path.rstrip("/") or "/"

    if route == "/api/health":
        return HTTPStatus.OK, {"status": "ok", "service": "ferluna-backend"}

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
    client_id: str | None = None,
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
        return resolve_admin_login(body, client_id)

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

        expected_revision = body.get("expectedRevision")
        if expected_revision is not None and (
            isinstance(expected_revision, bool) or not isinstance(expected_revision, int)
        ):
            return HTTPStatus.BAD_REQUEST, {
                "error": "invalid_payload",
                "message": "expectedRevision must be an integer",
            }

        return with_value_errors(
            lambda: replace_admin_site_payload(body, expected_revision)
        )

    return HTTPStatus.METHOD_NOT_ALLOWED, {
        "error": "method_not_allowed",
        "message": f"{method} is not allowed for {route}",
    }


def resolve_admin_login(
    body: dict[str, Any],
    client_id: str | None = None,
) -> tuple[int, dict[str, Any]]:
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
        if client_id is not None and login_rate_limited(client_id):
            return HTTPStatus.TOO_MANY_REQUESTS, {
                "error": "too_many_requests",
                "message": "Too many login attempts; try again later",
            }
        if not verify_admin_password(password):
            return HTTPStatus.UNAUTHORIZED, {
                "error": "unauthorized",
                "message": "Invalid admin credentials",
            }
        reset_login_attempts(client_id)
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
