from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.models import ArticleCandidate
from app.ingestion import RssFetcher, RssFetchError, ingest_rss

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "rss"
FEED_URL = "https://example.com/rss.xml"


def _ingest_fixture(name: str) -> list[ArticleCandidate]:
    body = (FIXTURES / name).read_bytes()
    return ingest_rss(FEED_URL, fetcher=RssFetcher(fetch=lambda _url: body))


def test_valid_feed_with_multiple_entries() -> None:
    candidates = _ingest_fixture("valid_multiple.xml")
    assert [candidate.title for candidate in candidates] == [
        "First Article",
        "Second Article",
    ]
    assert [candidate.canonical_url for candidate in candidates] == [
        "https://example.com/articles/1",
        "https://example.com/articles/2",
    ]


def test_missing_excerpt_is_none() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    missing = next(c for c in candidates if c.title == "Missing excerpt")
    assert missing.excerpt is None


def test_missing_publication_date_is_none() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    missing = next(c for c in candidates if c.title == "Missing publication date")
    assert missing.published_at is None
    assert missing.excerpt == "Excerpt without a date"


def test_missing_article_url_is_skipped() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    assert all(c.title != "Missing article URL" for c in candidates)


def test_missing_title_is_skipped() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    urls = [c.canonical_url for c in candidates]
    assert "https://example.com/articles/no-title" not in urls


def test_blank_title_is_skipped() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    urls = [c.canonical_url for c in candidates]
    assert "https://example.com/articles/blank-title" not in urls


def test_malformed_entries_do_not_break_valid_entries() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    titles = [c.title for c in candidates]
    assert "Has excerpt and date" in titles
    assert "Still valid after malformed siblings" in titles
    assert "Invalid article URL" not in titles
    assert len(candidates) == 5


def test_unusable_feed_raises_rss_fetch_error() -> None:
    with pytest.raises(RssFetchError, match="Unparseable RSS feed"):
        _ingest_fixture("unusable.xml")


def test_empty_response_raises_rss_fetch_error() -> None:
    fetcher = RssFetcher(fetch=lambda _url: b"   ")
    with pytest.raises(RssFetchError, match="Empty RSS response"):
        ingest_rss(FEED_URL, fetcher=fetcher)


def test_network_failure_raises_rss_fetch_error() -> None:
    def boom(_url: str) -> bytes:
        raise TimeoutError("connection timed out")

    with pytest.raises(RssFetchError, match="Failed to fetch RSS feed"):
        ingest_rss(FEED_URL, fetcher=RssFetcher(fetch=boom))


def test_valid_feed_with_zero_items_returns_empty_list() -> None:
    assert _ingest_fixture("empty_feed.xml") == []


def test_publication_date_is_converted_to_datetime() -> None:
    candidates = _ingest_fixture("valid_multiple.xml")
    assert candidates[0].published_at == datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    assert candidates[1].published_at == datetime(2026, 8, 31, 15, 30, 0, tzinfo=UTC)


def test_source_url_is_preserved_on_every_candidate() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    assert candidates
    assert all(c.source_url == FEED_URL for c in candidates)


def test_html_summary_becomes_plain_text_excerpt() -> None:
    candidates = _ingest_fixture("mixed_entries.xml")
    html_entry = next(c for c in candidates if c.title == "HTML excerpt")
    assert html_entry.excerpt == "Hello world."


def test_fetcher_returns_unusable_entries_without_filtering() -> None:
    body = (FIXTURES / "mixed_entries.xml").read_bytes()
    entries = RssFetcher(fetch=lambda _url: body).fetch_entries(FEED_URL)
    titles = [entry.title for entry in entries]
    assert "Missing article URL" in titles
    assert any((entry.title or "").strip() == "" for entry in entries)
    assert any(entry.link == "not-a-url" for entry in entries)
    assert len(entries) == 9
