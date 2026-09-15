from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.domain_errors import DomainError
from app.domain.payment.mock import MockPaymentProvider, get_payment_provider

pytestmark = pytest.mark.anyio


def _fake_order(number: str = "NS-240101-ABC123", total: str = "31.98") -> SimpleNamespace:
    """The provider only reads number/total/currency, so a stub is enough."""
    return SimpleNamespace(number=number, total=Decimal(total), currency_code="USD")


async def test_intent_then_confirm_succeeds():
    provider = MockPaymentProvider()
    intent = await provider.create_intent(_fake_order())

    assert intent.provider == "mock"
    assert intent.amount == Decimal("31.98")
    assert intent.currency == "USD"
    assert intent.status == "requires_confirmation"

    result = await provider.confirm(intent.provider_ref)
    assert result.success is True
    assert result.provider_ref == intent.provider_ref


async def test_confirming_an_unknown_reference_fails():
    provider = MockPaymentProvider()

    result = await provider.confirm("mock_does_not_exist")

    assert result.success is False
    assert result.raw["reason"] == "unknown_intent"


async def test_refund_before_capture_is_refused():
    provider = MockPaymentProvider()
    intent = await provider.create_intent(_fake_order())

    result = await provider.refund(intent.provider_ref, Decimal("10.00"))

    assert result.success is False
    assert result.raw["reason"] == "not_captured"


async def test_refund_after_capture_succeeds():
    provider = MockPaymentProvider()
    intent = await provider.create_intent(_fake_order())
    await provider.confirm(intent.provider_ref)

    result = await provider.refund(intent.provider_ref, Decimal("31.98"))

    assert result.success is True
    assert result.raw["refunded"] == "31.98"


async def test_registry_exposes_the_mock_provider():
    provider = get_payment_provider("mock")
    assert provider.code == "mock"


async def test_unknown_provider_lists_what_is_available():
    with pytest.raises(DomainError) as exc:
        get_payment_provider("stripe")

    assert exc.value.code == "UNKNOWN_PAYMENT_PROVIDER"
    assert "mock" in exc.value.details["available"]
