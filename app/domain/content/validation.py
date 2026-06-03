from __future__ import annotations

from math import isfinite
from typing import Any

from app.domain.content.visibility import DEFAULT_VISUAL_SETTINGS, optional_datetime

MAX_ADMIN_COLLECTION_SIZE = 250
LINK_KINDS = {"github", "linkedin", "mail", "web"}


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
        require_number(section, "angle"),
        require_int(section, "order"),
        optional_datetime(section.get("visibleFrom")),
        optional_datetime(section.get("visibleUntil")),
        require_bool(section, "enabled"),
    )


def build_visual_settings_row(value: Any) -> tuple[Any, ...]:
    if value is None:
        value = DEFAULT_VISUAL_SETTINGS
    if not isinstance(value, dict):
        raise ValueError("visualSettings must be an object")

    return (
        require_positive_number(value, "sectionOrbitDurationSeconds"),
        require_positive_number(value, "momentaryOrbitDurationSeconds"),
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
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{key} must be a finite number")
    return number


def require_positive_number(payload: dict[str, Any], key: str) -> float:
    number = require_number(payload, key)
    if number <= 0:
        raise ValueError(f"{key} must be greater than 0")
    return number


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


def require_link_kind(payload: dict[str, Any]) -> str:
    kind = require_text(payload, "kind")
    if kind not in LINK_KINDS:
        raise ValueError("link kind must be github, linkedin, mail or web")
    return kind
