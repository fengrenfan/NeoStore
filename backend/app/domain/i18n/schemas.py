from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LocaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    is_default: bool


class TranslationInput(BaseModel):
    """Payload shape for admin writes: one entry per locale."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    description: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
