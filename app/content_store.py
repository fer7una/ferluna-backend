from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.content_config import content_config_payload

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
MAX_ADMIN_COLLECTION_SIZE = 250
LINK_KINDS = {"github", "linkedin", "mail", "web"}


class DatabaseDisabledError(RuntimeError):
    pass


class DatabaseDependencyError(RuntimeError):
    pass


class RevisionConflictError(RuntimeError):
    pass


def database_url() -> str | None:
    return os.environ.get("FERLUNA_DATABASE_URL")


def public_site_payload() -> dict[str, object]:
    if not database_url():
        return filter_public_config(content_config_payload())

    return filter_public_config(load_admin_site_payload())


def load_admin_site_payload() -> dict[str, object]:
    if not database_url():
        payload = content_config_payload()
        payload["revision"] = 0
        return payload

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, role, tagline, location, email, avatar_alt, highlights
                FROM site_profile
                WHERE id = 'profile'
                """
            )
            profile_row = cur.fetchone()
            profile = profile_from_row(profile_row)

            # Only override links from the table when a profile row exists.
            # An initialized-but-unseeded database keeps the fallback links.
            if profile_row is not None:
                cur.execute(
                    """
                    SELECT id, label, href, kind
                    FROM profile_links
                    ORDER BY sort_order, id
                    """
                )
                profile["links"] = [link_from_row(row) for row in cur.fetchall()]

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

            cur.execute(
                """
                SELECT id, tab_id, kind, kicker, title, meta, description, href,
                       tags, icon_key, sort_order, visible_from, visible_until, featured
                FROM momentary_items
                ORDER BY tab_id, sort_order, id
                """
            )
            tab_items = [momentary_item_from_row(row) for row in cur.fetchall()]

            revision = read_revision(cur)

    return {
        "profile": profile,
        "sections": sections,
        "sectionItems": items,
        "momentaryTabs": tabs,
        "momentaryItems": tab_items,
        "revision": revision,
    }


def replace_admin_site_payload(
    payload: dict[str, Any],
    expected_revision: int | None = None,
) -> dict[str, object]:
    if not database_url():
        raise DatabaseDisabledError("FERLUNA_DATABASE_URL is not configured")

    # Validate everything up front so an invalid payload never touches the
    # database and the error is reported before any row is written.
    profile_row, link_rows = build_profile_rows(payload.get("profile"))
    sections = validate_collection(payload.get("sections"), "sections")
    items = validate_collection(payload.get("sectionItems"), "sectionItems")
    tabs = validate_collection(payload.get("momentaryTabs"), "momentaryTabs")
    tab_items = validate_collection(payload.get("momentaryItems"), "momentaryItems")

    section_ids = {require_text(section, "id") for section in sections}
    for item in items:
        section_id = require_text(item, "sectionId")
        if section_id not in section_ids:
            raise ValueError(
                f"Unknown sectionId for item {require_text(item, 'id')}: {section_id}"
            )

    tab_ids = {require_text(tab, "id") for tab in tabs}
    for tab_item in tab_items:
        tab_id = require_text(tab_item, "tabId")
        if tab_id not in tab_ids:
            raise ValueError(
                f"Unknown tabId for item {require_text(tab_item, 'id')}: {tab_id}"
            )

    section_rows = [build_section_row(section) for section in sections]
    item_rows = [build_item_row(item, "sectionId") for item in items]
    tab_rows = [build_tab_row(tab) for tab in tabs]
    tab_item_rows = [build_item_row(tab_item, "tabId") for tab_item in tab_items]

    with connect() as conn:
        with conn.cursor() as cur:
            current_revision = read_revision(cur)
            if expected_revision is not None and expected_revision != current_revision:
                raise RevisionConflictError(
                    "Content changed since it was loaded; reload before saving"
                )

            cur.execute("DELETE FROM section_items")
            cur.execute("DELETE FROM momentary_items")
            cur.execute("DELETE FROM site_sections")
            cur.execute("DELETE FROM momentary_tabs")
            cur.execute("DELETE FROM profile_links")
            cur.execute("DELETE FROM site_profile")

            cur.execute(
                """
                INSERT INTO site_profile (
                    id, name, role, tagline, location, email, avatar_alt,
                    highlights, updated_at
                )
                VALUES ('profile', %s, %s, %s, %s, %s, %s, %s, now())
                """,
                profile_row,
            )

            for link_row in link_rows:
                cur.execute(
                    """
                    INSERT INTO profile_links (id, label, href, kind, sort_order, updated_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    """,
                    link_row,
                )

            for section_row in section_rows:
                cur.execute(
                    """
                    INSERT INTO site_sections (
                        id, route, label, eyebrow, title, description, icon_key, orbit,
                        angle, sort_order, visible_from, visible_until, enabled, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    section_row,
                )

            for item_row in item_rows:
                cur.execute(
                    """
                    INSERT INTO section_items (
                        id, section_id, kind, kicker, title, meta, description, href,
                        tags, icon_key, sort_order, visible_from, visible_until,
                        featured, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    item_row,
                )

            for tab_row in tab_rows:
                cur.execute(
                    """
                    INSERT INTO momentary_tabs (
                        id, label, icon_key, angle, sort_order, visible_from,
                        visible_until, enabled, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    tab_row,
                )

            for tab_item_row in tab_item_rows:
                cur.execute(
                    """
                    INSERT INTO momentary_items (
                        id, tab_id, kind, kicker, title, meta, description, href,
                        tags, icon_key, sort_order, visible_from, visible_until,
                        featured, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    """,
                    tab_item_row,
                )

            cur.execute(
                """
                INSERT INTO site_revision (id, revision, updated_at)
                VALUES ('revision', %s, now())
                ON CONFLICT (id) DO UPDATE
                    SET revision = EXCLUDED.revision, updated_at = now()
                """,
                (current_revision + 1,),
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

    tabs = [
        tab
        for tab in payload["momentaryTabs"]
        if is_enabled_and_visible(tab, now)
    ]
    tab_ids = {tab["id"] for tab in tabs}

    return {
        "profile": payload["profile"],
        "sections": sorted(sections, key=lambda section: (section["order"], section["id"])),
        "sectionItems": [
            item
            for item in payload["sectionItems"]
            if item["sectionId"] in section_ids and is_visible(item, now)
        ],
        "momentaryTabs": sorted(tabs, key=lambda tab: (tab["order"], tab["id"])),
        "momentaryItems": [
            item
            for item in payload["momentaryItems"]
            if item["tabId"] in tab_ids and is_visible(item, now)
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


def read_revision(cur: Any) -> int:
    cur.execute("SELECT revision FROM site_revision WHERE id = 'revision'")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def profile_from_row(row: tuple[Any, ...] | None) -> dict[str, object]:
    if row is None:
        profile = content_config_payload()["profile"]
        return dict(profile)  # type: ignore[arg-type]

    return {
        "name": row[0],
        "role": row[1],
        "tagline": row[2],
        "location": row[3],
        "email": row[4],
        "avatarAlt": row[5],
        "highlights": list(row[6] or []),
        "links": [],
    }


def link_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {"label": row[1], "href": row[2], "kind": row[3]}


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


def _item_common(row: tuple[Any, ...]) -> dict[str, object]:
    return {
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


def item_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {"id": row[0], "sectionId": row[1], **_item_common(row)}


def momentary_item_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {"id": row[0], "tabId": row[1], **_item_common(row)}


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


def build_profile_rows(value: Any) -> tuple[tuple[Any, ...], list[tuple[Any, ...]]]:
    if not isinstance(value, dict):
        raise ValueError("profile must be an object")

    profile_row = (
        require_text(value, "name"),
        require_text(value, "role"),
        require_text(value, "tagline"),
        require_text(value, "location"),
        require_text(value, "email"),
        require_text(value, "avatarAlt"),
        require_text_list(value.get("highlights")),
    )

    raw_links = value.get("links")
    if raw_links is None:
        raw_links = []
    if not isinstance(raw_links, list):
        raise ValueError("links must be a list")
    if len(raw_links) > MAX_ADMIN_COLLECTION_SIZE:
        raise ValueError(f"links exceeds {MAX_ADMIN_COLLECTION_SIZE} entries")

    link_rows: list[tuple[Any, ...]] = []
    for index, raw_link in enumerate(raw_links, start=1):
        if not isinstance(raw_link, dict):
            raise ValueError("link entries must be objects")
        link_rows.append(
            (
                f"link-{index}",
                require_text(raw_link, "label"),
                require_text(raw_link, "href"),
                require_link_kind(raw_link),
                index * 10,
            )
        )

    return profile_row, link_rows


def build_section_row(section: dict[str, Any]) -> tuple[Any, ...]:
    return (
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
    )


def build_item_row(item: dict[str, Any], owner_key: str) -> tuple[Any, ...]:
    return (
        require_text(item, "id"),
        require_text(item, owner_key),
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
    )


def build_tab_row(tab: dict[str, Any]) -> tuple[Any, ...]:
    return (
        require_text(tab, "id"),
        require_text(tab, "label"),
        require_text(tab, "iconKey"),
        require_number(tab, "angle"),
        require_int(tab, "order"),
        optional_datetime(tab.get("visibleFrom")),
        optional_datetime(tab.get("visibleUntil")),
        require_bool(tab, "enabled"),
    )


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


def require_link_kind(payload: dict[str, Any]) -> str:
    kind = require_text(payload, "kind")
    if kind not in LINK_KINDS:
        raise ValueError("link kind must be github, linkedin, mail or web")
    return kind


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
