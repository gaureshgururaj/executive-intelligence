from app.domain.models import ArticleCandidate
from app.ingestion.arxiv import DEFAULT_ARXIV_QUERY, ingest_arxiv
from app.ingestion.arxiv_fetcher import ArxivFetcher
from app.ingestion.arxiv_normalize import normalize_arxiv_entry
from app.ingestion.errors import ArxivFetchError, RssFetchError
from app.ingestion.fetcher import RssFetcher
from app.ingestion.normalize import normalize_entry


def ingest_rss(
    feed_url: str, fetcher: RssFetcher | None = None
) -> list[ArticleCandidate]:
    """Fetch a feed and return validated article candidates. Skips unusable entries."""
    active_fetcher = fetcher or RssFetcher()
    candidates: list[ArticleCandidate] = []
    for entry in active_fetcher.fetch_entries(feed_url):
        candidate = normalize_entry(entry, source_url=feed_url)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


__all__ = [
    "ArxivFetchError",
    "ArxivFetcher",
    "DEFAULT_ARXIV_QUERY",
    "RssFetchError",
    "RssFetcher",
    "ingest_arxiv",
    "ingest_rss",
    "normalize_arxiv_entry",
    "normalize_entry",
]
