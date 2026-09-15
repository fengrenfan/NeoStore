from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.i18n.service import I18nService
from tests.factories import seed_locales


@dataclass
class FakeTranslation:
    locale: str
    text: str


@pytest.mark.anyio
async def test_resolve_locale_falls_back_to_default(db_session):
    await seed_locales(db_session)
    service = I18nService(db_session)

    assert await service.resolve_locale("en") == "en"
    assert await service.resolve_locale("ja") == "zh-CN"
    assert await service.resolve_locale(None) == "zh-CN"


@pytest.mark.anyio
async def test_resolve_locale_matches_language_prefix(db_session):
    await seed_locales(db_session)
    assert await I18nService(db_session).resolve_locale("en-GB") == "en"
    assert await I18nService(db_session).resolve_locale("zh_TW") == "zh-CN"


@pytest.mark.anyio
async def test_translate_prefers_requested_then_defaults(db_session):
    await seed_locales(db_session)
    rows = [FakeTranslation("zh-CN", "霓虹 T 恤"), FakeTranslation("en", "Neon Tee")]
    service = I18nService(db_session)

    assert (await service.translate(rows, "en")).text == "Neon Tee"
    assert (await service.translate(rows, "fr")).text == "霓虹 T 恤"
    assert await service.translate([], "en") is None


@pytest.mark.anyio
async def test_resolve_from_accept_language_walks_the_header(db_session):
    await seed_locales(db_session)
    service = I18nService(db_session)

    assert await service.resolve_from_accept_language("fr-FR,en;q=0.8") == "en"
    assert await service.resolve_from_accept_language("de,it;q=0.5") == "zh-CN"
    assert await service.resolve_from_accept_language(None) == "zh-CN"


@pytest.mark.anyio
async def test_default_locale_comes_from_the_database(db_session):
    await seed_locales(db_session)
    assert await I18nService(db_session).default_locale() == "zh-CN"
