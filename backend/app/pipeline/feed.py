from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.domain.models import ArticleCandidate
from app.ingestion import ingest_rss
from app.ingestion.fetcher import RssFetcher
from app.llm.client import LlmClient
from app.pipeline.results import PipelineItem
from app.pipeline.trend import TrendPipeline
from app.quality import QualityGate

if TYPE_CHECKING:
    from app.repositories.articles import StoredArticle


@dataclass(frozen=True)
class FeedItemResult:
    item: PipelineItem | None
    stored: StoredArticle | None
    skipped: bool = False


def _rss_fields_unchanged(candidate: ArticleCandidate, stored: StoredArticle) -> bool:
    return (
        candidate.title == stored.title
        and candidate.excerpt == stored.excerpt
        and candidate.published_at == stored.published_at
    )


class FeedIngestion:
    """RSS → TrendPipeline → ArticleRepository. Does not commit."""

    def __init__(
        self,
        llm: LlmClient,
        quality_gate: QualityGate | None = None,
    ) -> None:
        self._pipeline = TrendPipeline(llm, quality_gate)

    def run(
        self,
        feed_url: str,
        session: Session,
        *,
        max_articles: int | None = None,
        fetcher: RssFetcher | None = None,
    ) -> list[FeedItemResult]:
        from app.repositories.articles import ArticleRepository

        candidates = ingest_rss(feed_url, fetcher=fetcher)
        if max_articles is not None:
            candidates = candidates[:max_articles]

        repository = ArticleRepository(session)
        known = repository.get_by_canonical_urls(
            [str(candidate.canonical_url) for candidate in candidates]
        )

        to_process: list[ArticleCandidate] = []
        skipped_by_url: dict[str, StoredArticle] = {}
        for candidate in candidates:
            url = str(candidate.canonical_url)
            stored = known.get(url)
            if stored is not None and _rss_fields_unchanged(candidate, stored):
                skipped_by_url[url] = stored
            else:
                to_process.append(candidate)

        processed_by_url = {
            str(item.candidate.canonical_url): item
            for item in self._pipeline.process_candidates(to_process)
        }

        results: list[FeedItemResult] = []
        for candidate in candidates:
            url = str(candidate.canonical_url)
            if url in skipped_by_url:
                results.append(
                    FeedItemResult(
                        item=None,
                        stored=skipped_by_url[url],
                        skipped=True,
                    )
                )
                continue
            item = processed_by_url[url]
            if item.error is not None:
                results.append(FeedItemResult(item=item, stored=None, skipped=False))
            else:
                stored = repository.save_pipeline_item(item)
                results.append(FeedItemResult(item=item, stored=stored, skipped=False))
        return results
