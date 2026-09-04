from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app.domain.models import PaperCandidate
from app.ingestion import (
    DEFAULT_ARXIV_QUERY,
    ArxivFetcher,
    ArxivFetchError,
    ingest_arxiv,
)
from app.ingestion.arxiv_fetcher import ARXIV_API_URL, build_arxiv_query_url

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "arxiv"
QUERY = DEFAULT_ARXIV_QUERY
MAX_RESULTS = 20


def _ingest_fixture(
    name: str, *, max_results: int = MAX_RESULTS
) -> list[PaperCandidate]:
    body = (FIXTURES / name).read_bytes()
    return ingest_arxiv(
        QUERY,
        max_results=max_results,
        fetcher=ArxivFetcher(fetch=lambda _url: body),
    )


def test_valid_feed_with_multiple_entries_preserves_order() -> None:
    papers = _ingest_fixture("valid_multiple.xml")
    assert [paper.arxiv_id for paper in papers] == ["2401.00001", "2401.00002"]
    assert [paper.title for paper in papers] == ["First Paper", "Second Paper"]


def test_request_includes_query_max_results_and_submission_sort() -> None:
    seen: list[str] = []
    body = (FIXTURES / "valid_multiple.xml").read_bytes()

    def fetch(url: str) -> bytes:
        seen.append(url)
        return body

    ingest_arxiv(QUERY, max_results=7, fetcher=ArxivFetcher(fetch=fetch))

    assert len(seen) == 1
    parsed = urlparse(seen[0])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == ARXIV_API_URL
    params = parse_qs(parsed.query)
    assert params["search_query"] == [QUERY]
    assert params["max_results"] == ["7"]
    assert params["start"] == ["0"]
    assert params["sortBy"] == ["submittedDate"]
    assert params["sortOrder"] == ["descending"]


def test_build_arxiv_query_url_matches_fetcher() -> None:
    url = build_arxiv_query_url(QUERY, 3)
    params = parse_qs(urlparse(url).query)
    assert params["max_results"] == ["3"]


@pytest.mark.parametrize("max_results", [0, -1])
def test_max_results_must_be_positive(max_results: int) -> None:
    def boom(_url: str) -> bytes:
        raise AssertionError("fetch must not run for invalid max_results")

    with pytest.raises(ValueError, match="max_results must be greater than 0"):
        ingest_arxiv(QUERY, max_results=max_results, fetcher=ArxivFetcher(fetch=boom))
    with pytest.raises(ValueError, match="max_results must be greater than 0"):
        ArxivFetcher(fetch=boom).fetch_entries(QUERY, max_results)


def test_modern_arxiv_id_is_unversioned() -> None:
    papers = _ingest_fixture("valid_multiple.xml")
    assert papers[0].arxiv_id == "2401.00001"


def test_version_suffix_is_stripped() -> None:
    papers = _ingest_fixture("valid_multiple.xml")
    assert papers[1].arxiv_id == "2401.00002"
    assert "v2" not in papers[1].arxiv_id
    assert papers[1].paper_url.endswith("2401.00002v2")


def test_old_style_arxiv_id_is_unversioned() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    old = next(paper for paper in papers if paper.title == "Old Style Identifier")
    assert old.arxiv_id == "hep-th/9901001"


def test_title_and_abstract_whitespace_is_collapsed() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    collapsed = next(paper for paper in papers if paper.arxiv_id == "2401.33333")
    assert collapsed.title == "Large Language Models"
    assert collapsed.abstract == "An abstract with extra whitespace."


def test_authors_are_parsed_and_blanks_removed() -> None:
    multiple = _ingest_fixture("valid_multiple.xml")
    assert multiple[1].authors == ["Alan Turing", "Grace Hopper"]
    collapsed = next(
        paper
        for paper in _ingest_fixture("mixed_entries.xml")
        if paper.arxiv_id == "2401.33333"
    )
    assert collapsed.authors == ["Whitespace Author"]


def test_categories_are_parsed_and_blanks_removed() -> None:
    multiple = _ingest_fixture("valid_multiple.xml")
    assert multiple[1].categories == ["cs.LG", "cs.CL"]
    collapsed = next(
        paper
        for paper in _ingest_fixture("mixed_entries.xml")
        if paper.arxiv_id == "2401.33333"
    )
    assert collapsed.categories == ["cs.CL"]


def test_paper_url_is_the_abstract_page() -> None:
    papers = _ingest_fixture("valid_multiple.xml")
    assert papers[0].paper_url == "http://arxiv.org/abs/2401.00001v1"


def test_pdf_url_is_populated_when_present() -> None:
    papers = _ingest_fixture("valid_multiple.xml")
    assert papers[0].pdf_url == "http://arxiv.org/pdf/2401.00001v1"


def test_missing_pdf_url_is_none() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    missing = next(paper for paper in papers if paper.title == "Missing pdf")
    assert missing.pdf_url is None
    assert missing.arxiv_id == "2401.22222"
    assert missing.paper_url == "http://arxiv.org/abs/2401.22222v1"


def test_missing_title_is_skipped() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    assert all(paper.arxiv_id != "2401.55555" for paper in papers)


def test_missing_id_is_skipped() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    assert all(paper.title != "Missing identifier" for paper in papers)


def test_invalid_id_is_skipped() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    assert all(paper.title != "Invalid identifier" for paper in papers)


def test_missing_abstract_is_skipped() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    assert all(paper.arxiv_id != "2401.77777" for paper in papers)


def test_no_authors_is_skipped() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    assert all(paper.arxiv_id != "2401.88888" for paper in papers)


def test_invalid_paper_url_is_skipped() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    assert all(paper.arxiv_id != "2401.99991" for paper in papers)


def test_malformed_entries_do_not_break_valid_entries() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    titles = [paper.title for paper in papers]
    assert "Has pdf and dates" in titles
    assert "Still valid after malformed siblings" in titles
    assert "Invalid identifier" not in titles
    assert "No authors" not in titles
    assert len(papers) == 6


def test_missing_published_and_updated_are_none() -> None:
    papers = _ingest_fixture("mixed_entries.xml")
    missing = next(paper for paper in papers if paper.title == "Missing dates")
    assert missing.published_at is None
    assert missing.updated_at is None


def test_publication_dates_are_converted_to_datetime() -> None:
    papers = _ingest_fixture("valid_multiple.xml")
    assert papers[0].published_at == datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    assert papers[1].updated_at == datetime(2026, 9, 3, 9, 0, 0, tzinfo=UTC)


def test_valid_feed_with_zero_items_returns_empty_list() -> None:
    assert _ingest_fixture("empty_feed.xml") == []


def test_empty_response_raises_arxiv_fetch_error() -> None:
    fetcher = ArxivFetcher(fetch=lambda _url: b"   ")
    with pytest.raises(ArxivFetchError, match="Empty arXiv response"):
        ingest_arxiv(QUERY, max_results=MAX_RESULTS, fetcher=fetcher)


def test_unusable_feed_raises_arxiv_fetch_error() -> None:
    with pytest.raises(ArxivFetchError, match="Unparseable arXiv feed"):
        _ingest_fixture("unusable.xml")


def test_network_failure_raises_arxiv_fetch_error() -> None:
    def boom(_url: str) -> bytes:
        raise TimeoutError("connection timed out")

    with pytest.raises(ArxivFetchError, match="Failed to fetch arXiv results"):
        ingest_arxiv(QUERY, max_results=MAX_RESULTS, fetcher=ArxivFetcher(fetch=boom))


def test_fetcher_returns_unusable_entries_without_filtering() -> None:
    body = (FIXTURES / "mixed_entries.xml").read_bytes()
    entries = ArxivFetcher(fetch=lambda _url: body).fetch_entries(QUERY, MAX_RESULTS)
    titles = [entry.title for entry in entries]
    assert "Missing identifier" in titles
    assert any(entry.pdf_url is None for entry in entries)
    assert any(entry.raw_id == "http://arxiv.org/abs/not-valid" for entry in entries)
    assert len(entries) == 12
