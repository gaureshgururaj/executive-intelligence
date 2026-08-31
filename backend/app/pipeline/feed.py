from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

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
    item: PipelineItem
    stored: StoredArticle | None


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
        items = self._pipeline.process_candidates(candidates)
        repository = ArticleRepository(session)
        results: list[FeedItemResult] = []
        for item in items:
            if item.error is not None:
                result = FeedItemResult(item=item, stored=None)
            else:
                stored = repository.save_pipeline_item(item)
                result = FeedItemResult(item=item, stored=stored)
            results.append(result)
        return results
