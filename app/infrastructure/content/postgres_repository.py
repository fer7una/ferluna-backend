from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.content_config import content_config_payload
from app.domain.content.exceptions import (
    DatabaseDependencyError,
    DatabaseDisabledError,
    RevisionConflictError,
)
from app.domain.content.validation import (
    build_item_row,
    build_profile_rows,
    build_section_row,
    build_tab_row,
    build_visual_settings_row,
    require_text,
    validate_collection,
)
from app.domain.content.visibility import DEFAULT_VISUAL_SETTINGS, serialize_datetime

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"
_schema_ready = False
_schema_lock = threading.Lock()


def database_url() -> str | None:
    return os.environ.get("FERLUNA_DATABASE_URL")


def ensure_database_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return

    with _schema_lock:
        if _schema_ready:
            return
        initialize_database()
        _schema_ready = True


def load_site_payload_from_database() -> dict[str, object]:
    ensure_database_schema()

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
                SELECT section_orbit_duration_seconds, momentary_orbit_duration_seconds
                FROM site_visual_settings
                WHERE id = 'visual'
                """
            )
            visual_settings = visual_settings_from_row(cur.fetchone())

            cur.execute(
                """
                SELECT id, route, label, eyebrow, title, description, icon_key,
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
        "visualSettings": visual_settings,
        "sections": sections,
        "sectionItems": items,
        "momentaryTabs": tabs,
        "momentaryItems": tab_items,
        "revision": revision,
    }


def replace_site_payload_in_database(
    payload: dict[str, Any],
    expected_revision: int | None = None,
) -> dict[str, object]:
    ensure_database_schema()

    profile_row, link_rows = build_profile_rows(payload.get("profile"))
    visual_settings_row = build_visual_settings_row(payload.get("visualSettings"))
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
            cur.execute("DELETE FROM site_visual_settings")

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

            cur.execute(
                """
                INSERT INTO site_visual_settings (
                    id, section_orbit_duration_seconds,
                    momentary_orbit_duration_seconds, updated_at
                )
                VALUES ('visual', %s, %s, now())
                """,
                visual_settings_row,
            )

            for section_row in section_rows:
                cur.execute(
                    """
                    INSERT INTO site_sections (
                        id, route, label, eyebrow, title, description, icon_key,
                        angle, sort_order, visible_from, visible_until, enabled, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
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

    return load_site_payload_from_database()


def initialize_database() -> None:
    if not database_url():
        raise DatabaseDisabledError("FERLUNA_DATABASE_URL is not configured")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()

    global _schema_ready
    _schema_ready = True


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


def visual_settings_from_row(row: tuple[Any, ...] | None) -> dict[str, object]:
    if row is None:
        return dict(DEFAULT_VISUAL_SETTINGS)

    return {
        "sectionOrbitDurationSeconds": row[0],
        "momentaryOrbitDurationSeconds": row[1],
    }


def section_from_row(row: tuple[Any, ...]) -> dict[str, object]:
    return {
        "id": row[0],
        "route": row[1],
        "label": row[2],
        "eyebrow": row[3],
        "title": row[4],
        "description": row[5],
        "iconKey": row[6],
        "angle": row[7],
        "order": row[8],
        "visibleFrom": serialize_datetime(row[9]),
        "visibleUntil": serialize_datetime(row[10]),
        "enabled": row[11],
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
