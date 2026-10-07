"""UTC time helpers. All datetimes are stored naive in UTC and rendered as ISO-8601 with 'Z'."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso(dt: datetime | None) -> str | None:
    """API rendering: second precision, 'Z' suffix."""
    if dt is None:
        return None
    return to_naive_utc(dt).replace(microsecond=0).isoformat() + "Z"


def iso_precise(dt: datetime) -> str:
    """Hash-chain rendering: microsecond precision, stable across SQLite/PostgreSQL."""
    return to_naive_utc(dt).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
