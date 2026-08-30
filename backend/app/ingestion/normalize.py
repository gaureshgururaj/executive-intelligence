import time
from datetime import UTC, datetime
from html.parser import HTMLParser

from pydantic import ValidationError

from app.domain.models import ArticleCandidate
from app.ingestion.fetcher import RawFeedEntry


class _PlainTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"}:
            self._chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self._chunks.append(" ")

    def text(self) -> str:
        return " ".join("".join(self._chunks).split())


def _html_to_plain_text(value: str) -> str | None:
    extractor = _PlainTextExtractor()
    try:
        extractor.feed(value)
        extractor.close()
    except Exception:
        return None
    return extractor.text() or None


def _excerpt_from_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    stripped = summary.strip()
    if not stripped:
        return None
    return _html_to_plain_text(stripped)


def _published_at(value: time.struct_time | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime(*value[:6], tzinfo=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_entry(entry: RawFeedEntry, *, source_url: str) -> ArticleCandidate | None:
    title = (entry.title or "").strip()
    if not title:
        return None

    canonical_url = (entry.link or "").strip()
    if not canonical_url:
        return None

    try:
        return ArticleCandidate(
            source_url=source_url,
            canonical_url=canonical_url,
            title=title,
            excerpt=_excerpt_from_summary(entry.summary),
            published_at=_published_at(entry.published_parsed),
        )
    except ValidationError:
        return None
