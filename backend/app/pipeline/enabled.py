from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ingestion.fetcher import RssFetcher
from app.pipeline.feed import FeedIngestion, FeedItemResult
from app.repositories.sources import SourceRepository, StoredSource

SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class SourceRunResult:
    source_id: uuid.UUID
    source_name: str
    source_url: str
    processed: int
    persisted: int
    accepted: int
    rejected: int
    failed: int
    error: str | None


def _empty_result(source: StoredSource, error: str) -> SourceRunResult:
    return SourceRunResult(
        source_id=source.id,
        source_name=source.name,
        source_url=source.url,
        processed=0,
        persisted=0,
        accepted=0,
        rejected=0,
        failed=0,
        error=error,
    )


def _summarize(source: StoredSource, items: list[FeedItemResult]) -> SourceRunResult:
    persisted = 0
    accepted = 0
    rejected = 0
    failed = 0
    for result in items:
        if result.item.error is not None:
            failed += 1
        if result.stored is not None:
            persisted += 1
            if result.item.decision is not None and result.item.decision.accepted:
                accepted += 1
            else:
                rejected += 1
    return SourceRunResult(
        source_id=source.id,
        source_name=source.name,
        source_url=source.url,
        processed=len(items),
        persisted=persisted,
        accepted=accepted,
        rejected=rejected,
        failed=failed,
        error=None,
    )


class EnabledSourceIngestionRunner:
    """Ingest every enabled source. One commit/rollback per source."""

    def __init__(
        self,
        session_factory: SessionFactory,
        ingestion: FeedIngestion,
    ) -> None:
        self._session_factory = session_factory
        self._ingestion = ingestion

    def run(
        self,
        *,
        max_articles: int | None = None,
        fetcher: RssFetcher | None = None,
    ) -> list[SourceRunResult]:
        list_session = self._session_factory()
        try:
            sources = SourceRepository(list_session).list_enabled()
        finally:
            list_session.close()

        return [
            self._run_source(source, max_articles=max_articles, fetcher=fetcher)
            for source in sources
        ]

    def _run_source(
        self,
        source: StoredSource,
        *,
        max_articles: int | None,
        fetcher: RssFetcher | None,
    ) -> SourceRunResult:
        session = self._session_factory()
        try:
            items = self._ingestion.run(
                source.url,
                session,
                max_articles=max_articles,
                fetcher=fetcher,
            )
            session.commit()
            return _summarize(source, items)
        except Exception as exc:
            session.rollback()
            return _empty_result(source, str(exc))
        finally:
            session.close()
