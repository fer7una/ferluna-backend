from __future__ import annotations

from typing import Any

from app.content_config import content_config_payload
from app.domain.content.exceptions import DatabaseDisabledError
from app.domain.content.visibility import filter_public_config
from app.infrastructure.content.postgres_repository import (
    database_url,
    initialize_database,
    load_site_payload_from_database,
    replace_site_payload_in_database,
)


def public_site_payload() -> dict[str, object]:
    if not database_url():
        return filter_public_config(content_config_payload())

    return filter_public_config(load_admin_site_payload())


def load_admin_site_payload() -> dict[str, object]:
    if not database_url():
        payload = content_config_payload()
        payload["revision"] = 0
        return payload

    return load_site_payload_from_database()


def replace_admin_site_payload(
    payload: dict[str, Any],
    expected_revision: int | None = None,
) -> dict[str, object]:
    if not database_url():
        raise DatabaseDisabledError("FERLUNA_DATABASE_URL is not configured")

    return replace_site_payload_in_database(payload, expected_revision)


def seed_database() -> dict[str, object]:
    initialize_database()
    return replace_admin_site_payload(content_config_payload())
