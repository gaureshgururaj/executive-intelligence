from app.domain.models import ArticleCandidate
from app.ingestion.errors import RssFetchError
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


__all__ = ["RssFetchError", "RssFetcher", "ingest_rss", "normalize_entry"]
