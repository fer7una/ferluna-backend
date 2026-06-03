from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_VISUAL_SETTINGS = {
    "sectionOrbitDurationSeconds": 34.0,
    "momentaryOrbitDurationSeconds": 18.0,
}


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
        "visualSettings": payload.get("visualSettings", DEFAULT_VISUAL_SETTINGS),
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
