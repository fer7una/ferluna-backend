from __future__ import annotations

from http import HTTPStatus
from typing import Any

from app.domain.content.exceptions import (
    DatabaseDependencyError,
    DatabaseDisabledError,
    RevisionConflictError,
)


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
    except RevisionConflictError as error:
        return HTTPStatus.CONFLICT, {
            "error": "revision_conflict",
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
