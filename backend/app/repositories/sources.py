import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Source
from app.domain.models import HttpUrlString

SOURCE_TYPE_RSS = "rss"
OPENAI_NEWS_NAME = "OpenAI News"
OPENAI_NEWS_URL = "https://openai.com/news/rss.xml"


class StoredSource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    source_type: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SourceUpsert(BaseModel):
    name: str = Field(min_length=1)
    url: HttpUrlString
    source_type: str = Field(default=SOURCE_TYPE_RSS, min_length=1)
    enabled: bool = True

    @field_validator("name", "source_type", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


def _apply_upsert(source: Source, payload: SourceUpsert) -> None:
    source.name = payload.name
    source.url = payload.url
    source.source_type = payload.source_type
    source.enabled = payload.enabled
    source.updated_at = datetime.now(UTC)


class SourceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        *,
        name: str,
        url: str,
        source_type: str = SOURCE_TYPE_RSS,
        enabled: bool = True,
    ) -> StoredSource:
        payload = SourceUpsert(
            name=name,
            url=url,
            source_type=source_type,
            enabled=enabled,
        )
        source = self._session.scalar(select(Source).where(Source.url == payload.url))
        if source is None:
            source = Source()
            _apply_upsert(source, payload)
            self._session.add(source)
        else:
            _apply_upsert(source, payload)
        self._session.flush()
        return StoredSource.model_validate(source)

    def get_by_url(self, url: str) -> StoredSource | None:
        source = self._session.scalar(select(Source).where(Source.url == url))
        if source is None:
            return None
        return StoredSource.model_validate(source)

    def list_enabled(self) -> list[StoredSource]:
        rows = self._session.scalars(
            select(Source)
            .where(Source.enabled.is_(True))
            .order_by(Source.name.asc(), Source.id.asc())
        )
        return [StoredSource.model_validate(row) for row in rows]
