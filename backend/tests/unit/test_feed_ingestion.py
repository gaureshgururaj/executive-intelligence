import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models import ArticleCandidate
from app.ingestion.errors import RssFetchError
from app.llm.errors import LlmClientError
from app.pipeline import FeedIngestion, FeedItemResult
from app.quality import QualityGate

FEED_URL = "https://example.com/rss.xml"

ACCEPTED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/accepted",
    title="Accepted article",
    excerpt="Enough text for publication.",
    published_at=datetime(2026, 8, 30, tzinfo=UTC),
)

REJECTED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/rejected",
    title="Rejected article",
    excerpt="Low relevance item.",
    published_at=datetime(2026, 8, 30, tzinfo=UTC),
)

FAILED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/failed",
    title="Failed article",
    excerpt="This one will not parse.",
    published_at=datetime(2026, 8, 30, tzinfo=UTC),
)

ACCEPTED_JSON = json.dumps(
    {
        "summary": "This development matters for enterprise automation.",
        "category": "Agentic AI",
        "relevance_score": 0.9,
        "key_points": ["Enterprise automation", "Open tooling"],
    }
)

REJECTED_JSON = json.dumps(
    {
        "summary": "Minor product note with little strategic impact.",
        "category": "Other",
        "relevance_score": 0.2,
        "key_points": ["Minor product note"],
    }
)


class MappingLlmClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.complete_calls = 0

    def complete(self, prompt: str) -> str:
        self.complete_calls += 1
        for url, response in self.responses.items():
            if url in prompt:
                return response
        raise AssertionError(f"no LLM fixture for prompt: {prompt}")


def _mapping_llm() -> MappingLlmClient:
    return MappingLlmClient(
        {
            ACCEPTED.canonical_url: ACCEPTED_JSON,
            REJECTED.canonical_url: REJECTED_JSON,
            FAILED.canonical_url: "not json",
        }
    )


def _run(
    candidates: list[ArticleCandidate],
    llm: MappingLlmClient | None = None,
    *,
    max_articles: int | None = None,
) -> tuple[list[FeedItemResult], MagicMock, MagicMock]:
    client = llm or _mapping_llm()
    session = MagicMock()
    repository = MagicMock()
    with (
        patch("app.pipeline.feed.ingest_rss", return_value=candidates),
        patch("app.repositories.articles.ArticleRepository", return_value=repository),
    ):
        results = FeedIngestion(client, quality_gate=QualityGate()).run(
            FEED_URL,
            session,
            max_articles=max_articles,
        )
    return results, session, repository


def test_save_called_for_accepted_and_rejected_not_for_failed() -> None:
    results, _, repository = _run([ACCEPTED, REJECTED, FAILED])
    saved_items = [
        call.args[0] for call in repository.save_pipeline_item.call_args_list
    ]
    saved_urls = [str(item.candidate.canonical_url) for item in saved_items]

    assert repository.save_pipeline_item.call_count == 2
    assert saved_urls == [ACCEPTED.canonical_url, REJECTED.canonical_url]
    assert all(item.error is None for item in saved_items)
    assert saved_items[0].decision is not None and saved_items[0].decision.accepted
    assert saved_items[1].decision is not None and not saved_items[1].decision.accepted

    failed = results[2]
    assert failed.item.error is not None
    assert failed.stored is None
    assert FAILED.canonical_url not in saved_urls


def test_max_articles_slices_before_llm() -> None:
    llm = _mapping_llm()
    results, _, repository = _run(
        [ACCEPTED, REJECTED, FAILED],
        llm=llm,
        max_articles=2,
    )
    assert llm.complete_calls == 2
    assert [str(result.item.candidate.canonical_url) for result in results] == [
        ACCEPTED.canonical_url,
        REJECTED.canonical_url,
    ]
    assert repository.save_pipeline_item.call_count == 2


def test_session_is_not_committed_rolled_back_or_closed() -> None:
    _, session, _ = _run([ACCEPTED])
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()


def test_rss_fetch_error_propagates_without_saving() -> None:
    session = MagicMock()
    repository = MagicMock()
    with (
        patch(
            "app.pipeline.feed.ingest_rss",
            side_effect=RssFetchError("Unparseable RSS feed"),
        ),
        patch("app.repositories.articles.ArticleRepository", return_value=repository),
        pytest.raises(RssFetchError, match="Unparseable RSS feed"),
    ):
        FeedIngestion(_mapping_llm()).run(FEED_URL, session)
    repository.save_pipeline_item.assert_not_called()
    session.commit.assert_not_called()


def test_llm_client_error_is_not_persisted() -> None:
    class MixedLlmClient:
        def __init__(self) -> None:
            self.complete_calls = 0

        def complete(self, prompt: str) -> str:
            self.complete_calls += 1
            if FAILED.canonical_url in prompt:
                raise LlmClientError("LiteLLM completion failed for model test")
            if ACCEPTED.canonical_url in prompt:
                return ACCEPTED_JSON
            raise AssertionError(f"no LLM fixture for prompt: {prompt}")

    llm = MixedLlmClient()
    session = MagicMock()
    repository = MagicMock()
    with (
        patch("app.pipeline.feed.ingest_rss", return_value=[ACCEPTED, FAILED]),
        patch("app.repositories.articles.ArticleRepository", return_value=repository),
    ):
        results = FeedIngestion(llm, quality_gate=QualityGate()).run(FEED_URL, session)

    saved_urls = [
        str(call.args[0].candidate.canonical_url)
        for call in repository.save_pipeline_item.call_args_list
    ]
    assert llm.complete_calls == 2
    assert saved_urls == [ACCEPTED.canonical_url]
    assert results[1].stored is None
    assert results[1].item.error == "LiteLLM completion failed for model test"
