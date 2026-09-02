from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.ingestion.errors import RssFetchError
from app.pipeline import EnabledSourceIngestionRunner, SourceRunResult
from app.repositories.sources import StoredSource

NOW = datetime(2026, 9, 2, tzinfo=UTC)
URL_A = "https://example.com/a.xml"
URL_B = "https://example.com/b.xml"
URL_C = "https://example.com/c.xml"


class RecordingSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class StubIngestion:
    def __init__(self, behavior: dict[str, list[MagicMock] | Exception]) -> None:
        self.behavior = behavior
        self.calls: list[tuple[str, RecordingSession, int | None]] = []

    def run(
        self,
        feed_url: str,
        session: RecordingSession,
        *,
        max_articles: int | None = None,
        fetcher: object = None,
    ) -> list[MagicMock]:
        self.calls.append((feed_url, session, max_articles))
        result = self.behavior[feed_url]
        if isinstance(result, Exception):
            raise result
        return result


def _source(name: str, url: str) -> StoredSource:
    return StoredSource(
        id=uuid4(),
        name=name,
        url=url,
        source_type="rss",
        enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )


def _item(*, accepted: bool | None, error: str | None, stored: bool) -> MagicMock:
    result = MagicMock()
    result.item.error = error
    if accepted is None:
        result.item.decision = None
    else:
        result.item.decision.accepted = accepted
    result.stored = MagicMock() if stored else None
    return result


def _factory() -> tuple[list[RecordingSession], object]:
    sessions: list[RecordingSession] = []

    def factory() -> RecordingSession:
        session = RecordingSession()
        sessions.append(session)
        return session

    return sessions, factory


def test_zero_enabled_sources_returns_empty_list() -> None:
    sessions, factory = _factory()
    ingestion = StubIngestion({})
    with patch(
        "app.pipeline.enabled.SourceRepository.list_enabled",
        return_value=[],
    ):
        results = EnabledSourceIngestionRunner(factory, ingestion).run()

    assert results == []
    assert ingestion.calls == []
    assert len(sessions) == 1
    assert sessions[0].commit_calls == 0
    assert sessions[0].rollback_calls == 0
    assert sessions[0].close_calls == 1


def test_list_enabled_failure_propagates_and_closes_listing_session() -> None:
    sessions, factory = _factory()
    ingestion = StubIngestion({})
    with (
        patch(
            "app.pipeline.enabled.SourceRepository.list_enabled",
            side_effect=RuntimeError("database unavailable"),
        ),
        pytest.raises(RuntimeError, match="database unavailable"),
    ):
        EnabledSourceIngestionRunner(factory, ingestion).run()

    assert ingestion.calls == []
    assert len(sessions) == 1
    assert sessions[0].close_calls == 1


def test_successful_sources_use_distinct_sessions_and_commit() -> None:
    source_a = _source("A", URL_A)
    source_b = _source("B", URL_B)
    sessions, factory = _factory()
    ingestion = StubIngestion(
        {
            URL_A: [_item(accepted=True, error=None, stored=True)],
            URL_B: [_item(accepted=True, error=None, stored=True)],
        }
    )
    with patch(
        "app.pipeline.enabled.SourceRepository.list_enabled",
        return_value=[source_a, source_b],
    ):
        results = EnabledSourceIngestionRunner(factory, ingestion).run()

    assert len(sessions) == 3
    listing, session_a, session_b = sessions
    assert listing is not session_a
    assert listing is not session_b
    assert session_a is not session_b
    assert listing.close_calls == 1
    assert listing.commit_calls == 0
    assert listing.rollback_calls == 0
    assert session_a.commit_calls == 1
    assert session_a.rollback_calls == 0
    assert session_a.close_calls == 1
    assert session_b.commit_calls == 1
    assert session_b.rollback_calls == 0
    assert session_b.close_calls == 1
    assert ingestion.calls[0][1] is session_a
    assert ingestion.calls[1][1] is session_b
    assert [result.source_url for result in results] == [URL_A, URL_B]
    assert all(result.error is None for result in results)


def test_item_level_errors_still_commit() -> None:
    source = _source("A", URL_A)
    sessions, factory = _factory()
    items = [
        _item(accepted=True, error=None, stored=True),
        _item(accepted=False, error=None, stored=True),
        _item(accepted=None, error="LLM output is not valid JSON", stored=False),
    ]
    ingestion = StubIngestion({URL_A: items})
    with patch(
        "app.pipeline.enabled.SourceRepository.list_enabled",
        return_value=[source],
    ):
        results = EnabledSourceIngestionRunner(factory, ingestion).run()

    assert results == [
        SourceRunResult(
            source_id=source.id,
            source_name="A",
            source_url=URL_A,
            processed=3,
            persisted=2,
            accepted=1,
            rejected=1,
            failed=1,
            error=None,
        )
    ]
    ingest_session = sessions[1]
    assert ingest_session.commit_calls == 1
    assert ingest_session.rollback_calls == 0
    assert ingest_session.close_calls == 1


def test_source_level_failure_rolls_back_only_that_source() -> None:
    source_a = _source("A", URL_A)
    source_b = _source("B", URL_B)
    source_c = _source("C", URL_C)
    sessions, factory = _factory()
    ingestion = StubIngestion(
        {
            URL_A: [_item(accepted=True, error=None, stored=True)],
            URL_B: RssFetchError("Failed to fetch RSS feed"),
            URL_C: [_item(accepted=True, error=None, stored=True)],
        }
    )
    with patch(
        "app.pipeline.enabled.SourceRepository.list_enabled",
        return_value=[source_a, source_b, source_c],
    ):
        results = EnabledSourceIngestionRunner(factory, ingestion).run()

    listing, session_a, session_b, session_c = sessions
    assert len({id(session) for session in sessions}) == 4
    assert listing.close_calls == 1
    assert session_a.commit_calls == 1
    assert session_a.rollback_calls == 0
    assert session_a.close_calls == 1
    assert session_b.commit_calls == 0
    assert session_b.rollback_calls == 1
    assert session_b.close_calls == 1
    assert session_c.commit_calls == 1
    assert session_c.rollback_calls == 0
    assert session_c.close_calls == 1
    assert results[0].error is None
    assert results[1].error == "Failed to fetch RSS feed"
    assert results[1].processed == 0
    assert results[2].error is None


def test_database_error_rolls_back_only_that_source() -> None:
    source_a = _source("A", URL_A)
    source_b = _source("B", URL_B)
    sessions, factory = _factory()
    ingestion = StubIngestion(
        {
            URL_A: RuntimeError("flush failed"),
            URL_B: [_item(accepted=True, error=None, stored=True)],
        }
    )
    with patch(
        "app.pipeline.enabled.SourceRepository.list_enabled",
        return_value=[source_a, source_b],
    ):
        results = EnabledSourceIngestionRunner(factory, ingestion).run()

    _, session_a, session_b = sessions
    assert session_a.rollback_calls == 1
    assert session_a.commit_calls == 0
    assert session_a.close_calls == 1
    assert session_b.commit_calls == 1
    assert session_b.close_calls == 1
    assert results[0].error == "flush failed"
    assert results[1].error is None


def test_max_articles_is_forwarded_per_source() -> None:
    source_a = _source("A", URL_A)
    source_b = _source("B", URL_B)
    _, factory = _factory()
    ingestion = StubIngestion(
        {
            URL_A: [],
            URL_B: [],
        }
    )
    with patch(
        "app.pipeline.enabled.SourceRepository.list_enabled",
        return_value=[source_a, source_b],
    ):
        EnabledSourceIngestionRunner(factory, ingestion).run(max_articles=3)

    assert [call[2] for call in ingestion.calls] == [3, 3]
    assert [call[0] for call in ingestion.calls] == [URL_A, URL_B]
