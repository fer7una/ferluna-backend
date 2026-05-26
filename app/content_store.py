from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.content_config import content_config_payload
from app.data import site_payload as legacy_site_payload

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
MAX_ADMIN_COLLECTION_SIZE = 250


class DatabaseDisabledError(RuntimeError):
    pass


class DatabaseDependencyError(RuntimeError):
    pass


def database_url() -> str | None:
    return os.environ.get("FERLUNA_DATABASE_URL")


def public_site_payload() -> dict[str, object]:
    payload = legacy_site_payload()
    payload.update(content_config_payload())

    if not database_url():
        return payload

    admin_payload = load_admin_site_payload()
    payload.update(filter_public_config(admin_payload))
    return payload


def load_admin_site_payload() -> dict[str, object]:
    if not database_url():
        return content_config_payload()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, route, label, eyebrow, title, description, icon_key, orbit,
                       angle, sort_order, visible_from, visible_until, enabled
                FROM site_sections
                ORDER BY sort_order, id
                """
            )
            sections = [section_from_row(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, section_id, kind, kicker, title, meta, description, href,
                       tags, icon_key, sort_order, visible_from, visible_until, featured
                FROM section_items
                ORDER BY section_id, sort_order, id
                """
            )
            items = [item_from_row(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, label, icon_key, angle, sort_order, visible_from,
                       visible_until, enabled
                FROM momentary_tabs
                ORDER BY sort_order, id
                """
            )
            tabs = [momentary_tab_from_row(row) for row in cur.fetchall()]

    return {"sections": sections, "sectionItems": items, "momentaryTabs": tabs}


def replace_admin_site_payload(payload: dict[str, Any]) -> dict[str, object]:
    if not database_url():
        raise DatabaseDisabledError("FERLUNA_DATABASE_URL is not configured")

    sections = validate_collection(payload.get("sections"), "sections")
    items = validate_collection(payload.get("sectionItems"), "sectionItems")
    tabs = validate_collection(payload.get("momentaryTabs"), "momentaryTabs")
    section_ids = {require_text(section, "id") for section in sections}

    for item in items:
        section_id = require_text(item, "sectionId")
        if section_id not in section_ids:
            raise ValueError(f"Unknown sectionId for item {require_text(item, 'id')}: {section_id}")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM section_items")
            cur.execute("DELETE FROM momentary_tabs")
            cur.execute("DELETE FROM site_sections")

            for section in sections:
                cur.execute(
                    """
                    INSERT INTO site_sections (
                        id, route, label, eyebrow, title, description, icon_key, orbit,
                        angle, sort_order, visible_from, visible_until, enabled, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    (
                        require_text(section, "id"),
                        require_text(section, "route"),
                        require_text(section, "label"),
                        require_text(section, "eyebrow"),
                        require_text(section, "title"),
                        require_text(section, "description"),
                        require_text(section, "iconKey"),
                        require_orbit(section),
                        require_number(section, "angle"),
                        require_int(section, "order"),
                        optional_datetime(section.get("visibleFrom")),
                        optional_datetime(section.get("visibleUntil")),
                        require_bool(section, "enabled"),
                    ),
                )

            for item in items:
                cur.execute(
                    """
                    INSERT INTO section_items (
                        id, section_id, kind, kicker, title, meta, description, href,
                        tags, icon_key, sort_order, visible_from, visible_until,
                        featured, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    (
                        require_text(item, "id"),
                        require_text(item, "sectionId"),
                        require_text(item, "kind"),
                        require_text(item, "kicker"),
                        require_text(item, "title"),
                        optional_text(item.get("meta")),
                        require_text(item, "description"),
                        optional_text(item.get("href")),
                        require_text_list(item.get("tags")),
                        require_text(item, "iconKey"),
                        require_int(item, "order"),
                        optional_datetime(item.get("visibleFrom")),
                        optional_datetime(item.get("visibleUntil")),
                        require_bool(item, "featured"),
                    ),
                )

            for tab in tabs:
                cur.execute(
                    """
                    INSERT INTO momentary_tabs (
                        id, label, icon_key, angle, sort_order, visible_from,
                        visible_until, enabled, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    (
                        require_text(tab, "id"),
                        require_text(tab, "label"),
                        require_text(tab, "iconKey"),
                        require_number(tab, "angle"),
                        require_int(tab, "order"),
                        optional_datetime(tab.get("visibleFrom")),
                        optional_datetime(tab.get("visibleUntil")),
                        require_bool(tab, "enabled"),
                    ),
                )

        conn.commit()

    return load_admin_site_payload()


def initialize_database() -> None:
    if not database_url():
        raise DatabaseDisabledError("FERLUNA_DATABASE_URL is not configured")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()


def seed_database() -> dict[str, object]:
    initialize_database()
    return replace_admin_site_payload(content_config_payload())


def filter_public_config(payload: dict[str, object]) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    sections = [
        section
        for section in payload["sections"]
        if is_enabled_and_visible(section, now)
    ]
    section_ids = {section["id"] for section in sections}

    return {
        "sections": sorted(sections, key=lambda section: (section["order"], section["id"])),
        "sectionItems": [
            item
            for item in payload["sectionItems"]
            if item["sectionId"] in section_ids and is_visible(item, now)
        ],
        "momentaryTabs": [
            tab
            for tab in payload["momentaryTabs"]
            if is_enabled_and_visible(tab, now)
        ],
    }


@contextmanager
def connect() -> Iterator[Any]:
    url = database_url()
    if not url:
        raise DatabaseDisabledError("FERLUNA_DATABASE_URL is not configured")

    try:
        import psycopg
    except ImportError as exc:
        raise DatabaseDependencyError("Install psycopg[binary] to use PostgreSQL") from exc

    conn = psycopg.connect(url)
    try:
        yield conn
    finally:
        conn.close()


def section_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "id": row[0],
        "route": row[1],
        "label": row[2],
        "eyebrow": row[3],
        "title": row[4],
        "description": row[5],
        "iconKey": row[6],
        "orbit": row[7],
        "angle": row[8],
        "order": row[9],
        "visibleFrom": serialize_datetime(row[10]),
        "visibleUntil": serialize_datetime(row[11]),
        "enabled": row[12],
    }


def item_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "id": row[0],
        "sectionId": row[1],
        "kind": row[2],
        "kicker": row[3],
        "title": row[4],
        "meta": row[5],
        "description": row[6],
        "href": row[7],
        "tags": list(row[8] or []),
        "iconKey": row[9],
        "order": row[10],
        "visibleFrom": serialize_datetime(row[11]),
        "visibleUntil": serialize_datetime(row[12]),
        "featured": row[13],
    }


def momentary_tab_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "id": row[0],
        "label": row[1],
        "iconKey": row[2],
        "angle": row[3],
        "order": row[4],
        "visibleFrom": serialize_datetime(row[5]),
        "visibleUntil": serialize_datetime(row[6]),
        "enabled": row[7],
    }


def validate_collection(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    if len(value) > MAX_ADMIN_COLLECTION_SIZE:
        raise ValueError(f"{name} exceeds {MAX_ADMIN_COLLECTION_SIZE} entries")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{name} entries must be objects")
    return value


def require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional text fields must be strings or null")
    return value.strip() or None


def require_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("tags must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def require_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number")
    return float(value)


def require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def require_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def require_orbit(payload: dict[str, Any]) -> str:
    orbit = require_text(payload, "orbit")
    if orbit not in {"inner", "outer"}:
        raise ValueError("orbit must be inner or outer")
    return orbit


def optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Datetime fields must be ISO strings or null")
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def is_enabled_and_visible(payload: dict[str, Any], now: datetime) -> bool:
    return bool(payload.get("enabled")) and is_visible(payload, now)


def is_visible(payload: dict[str, Any], now: datetime) -> bool:
    visible_from = optional_datetime(payload.get("visibleFrom"))
    visible_until = optional_datetime(payload.get("visibleUntil"))
    if visible_from and now < visible_from:
        return False
    if visible_until and now >= visible_until:
        return False
    return True
