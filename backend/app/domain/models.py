from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)

_http_url_adapter = TypeAdapter(HttpUrl)


def _must_be_http_url(value: str) -> str:
    return str(_http_url_adapter.validate_python(value))


HttpUrlString = Annotated[str, AfterValidator(_must_be_http_url)]


class ArticleCandidate(BaseModel):
    source_url: HttpUrlString
    canonical_url: HttpUrlString
    title: str = Field(min_length=1)
    excerpt: str | None = None
    published_at: datetime | None = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("excerpt", mode="before")
    @classmethod
    def empty_excerpt_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class TrendAnalysis(BaseModel):
    summary: str = Field(min_length=1)
    category: str = Field(min_length=1)
    relevance_score: float = Field(ge=0.0, le=1.0)
    key_points: list[str] = Field(default_factory=list)

    @field_validator("summary", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("key_points")
    @classmethod
    def key_points_not_blank(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("key_points must not contain blank strings")
        return cleaned


class QualityDecision(BaseModel):
    accepted: bool
    reason: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def reason_required_when_rejected(self) -> "QualityDecision":
        if not self.accepted and not self.reason:
            raise ValueError("reason is required when accepted is false")
        return self
