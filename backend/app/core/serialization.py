"""Serialisation helpers for values that cross the wire.

Timestamps are stored as UTC. PostgreSQL hands them back timezone-aware
(``timestamp with time zone``), but SQLite has no such type: it returns a naive
``2026-09-15T07:51:52``. A browser doing ``new Date("2026-09-15T07:51:52")``
reads that as **local** time, so the same order shows up eight hours off in
CST depending only on which database is behind the API.

The offset is therefore stamped on at the edge instead of being inherited from
whatever the driver happened to do. One contract, every deployment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as an aware UTC datetime, assuming naive means UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dump(value: datetime) -> str:
    # `isoformat()` on an aware datetime includes the offset, which is the
    # whole point: `2026-09-15T07:51:52+00:00`.
    return as_utc(value).isoformat()


#: A timestamp that always reaches the client with an offset attached.
UtcDatetime = Annotated[datetime, AfterValidator(as_utc), PlainSerializer(_dump, return_type=str)]
