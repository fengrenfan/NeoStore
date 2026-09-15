"""Timestamps must reach the client with an offset attached.

PostgreSQL returns aware datetimes, SQLite returns naive ones. Without a rule at
the edge the same order renders eight hours apart in CST depending purely on the
database behind the API — and a browser reads a naive ``2026-09-15T07:51:52`` as
local time, silently.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from pydantic import BaseModel

from app.core.serialization import UtcDatetime, as_utc
from app.domain.currency.schemas import ExchangeRateRead
from app.domain.order.schemas import OrderEventRead


class _Stamp(BaseModel):
    at: UtcDatetime


def test_naive_timestamps_are_read_as_utc():
    payload = _Stamp(at=datetime(2026, 9, 15, 7, 51, 52)).model_dump(mode="json")
    assert payload["at"] == "2026-09-15T07:51:52+00:00"


def test_offsets_are_normalised_to_utc():
    payload = _Stamp(
        at=datetime(2026, 9, 15, 9, 51, 52, tzinfo=timezone(timedelta(hours=2)))
    ).model_dump(mode="json")
    assert payload["at"] == "2026-09-15T07:51:52+00:00"


def test_openapi_shape_is_a_string():
    # The generated schema has to describe what actually goes over the wire, or
    # the frontends' generated types will claim `datetime` and lie.
    assert _Stamp.model_json_schema()["properties"]["at"]["type"] == "string"


def test_order_events_serialise_with_an_offset():
    event = OrderEventRead.model_validate(
        {
            "from_status": "draft",
            "to_status": "awaiting_payment",
            "note": "intent:mock_1",
            "created_at": datetime(2026, 9, 15, 7, 51, 52),
        }
    )
    assert event.model_dump(mode="json")["created_at"].endswith("+00:00")


def test_exchange_rates_serialise_with_an_offset():
    rate = ExchangeRateRead.model_validate(
        {
            "base_code": "USD",
            "quote_code": "CNY",
            "rate": "7.18",
            "source": "manual",
            "fetched_at": datetime(2026, 9, 15, 0, 0, 0),
        }
    )
    assert rate.model_dump(mode="json")["fetched_at"] == "2026-09-15T00:00:00+00:00"


def test_as_utc_leaves_aware_values_alone():
    moment = datetime(2026, 9, 15, 7, 51, 52, tzinfo=UTC)
    assert as_utc(moment) is moment
