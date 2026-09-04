import re
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.domain.models import PaperCandidate
from app.ingestion.arxiv_fetcher import RawArxivEntry

_http_url_adapter = TypeAdapter(HttpUrl)
_VERSION_SUFFIX = re.compile(r"v\d+$", re.IGNORECASE)
_MODERN_ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}$")
_OLD_ARXIV_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*(?:\.[a-zA-Z][a-zA-Z0-9-]*)*/\d{7}$")


def _unversioned_arxiv_id(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if "://" in text or text.startswith("/"):
        path = urlparse(text).path
        marker = "/abs/"
        if marker not in path:
            return None
        text = path.split(marker, 1)[1]
    text = text.strip("/")
    text = _VERSION_SUFFIX.sub("", text)
    if not text:
        return None
    if _MODERN_ARXIV_ID.fullmatch(text) or _OLD_ARXIV_ID.fullmatch(text):
        return text
    return None


def _http_url_or_none(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return str(_http_url_adapter.validate_python(text))
    except ValidationError:
        return None


def _as_datetime(value: time.struct_time | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime(*value[:6], tzinfo=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _clean_names(values: list[str]) -> list[str]:
    return [item.strip() for item in values if item.strip()]


def normalize_arxiv_entry(entry: RawArxivEntry) -> PaperCandidate | None:
    arxiv_id = _unversioned_arxiv_id(entry.raw_id)
    if arxiv_id is None:
        return None

    paper_url = _http_url_or_none(entry.paper_url)
    if paper_url is None:
        paper_url = _http_url_or_none(entry.raw_id)
    if paper_url is None:
        return None

    try:
        return PaperCandidate(
            arxiv_id=arxiv_id,
            title=entry.title or "",
            abstract=entry.summary or "",
            authors=_clean_names(entry.authors),
            published_at=_as_datetime(entry.published_parsed),
            updated_at=_as_datetime(entry.updated_parsed),
            paper_url=paper_url,
            pdf_url=_http_url_or_none(entry.pdf_url),
            categories=_clean_names(entry.categories),
        )
    except ValidationError:
        return None
