import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.domain.models import ArticleCandidate
from app.ingestion.errors import RssFetchError
from app.llm.errors import LlmClientError
from app.pipeline import TrendPipeline
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


def _pipeline(llm: MappingLlmClient | None = None) -> TrendPipeline:
    client = llm or MappingLlmClient(
        {
            ACCEPTED.canonical_url: ACCEPTED_JSON,
            REJECTED.canonical_url: REJECTED_JSON,
            FAILED.canonical_url: "not json",
        }
    )
    return TrendPipeline(llm=client, quality_gate=QualityGate())


def test_multiple_candidates_flow_through_agent_and_gate() -> None:
    pipeline = _pipeline()
    with patch(
        "app.pipeline.trend.ingest_rss",
        return_value=[ACCEPTED, REJECTED, FAILED],
    ):
        items = pipeline.run(FEED_URL)

    assert [item.candidate.canonical_url for item in items] == [
        ACCEPTED.canonical_url,
        REJECTED.canonical_url,
        FAILED.canonical_url,
    ]
    assert items[0].decision is not None and items[0].decision.accepted is True
    assert items[1].decision is not None and items[1].decision.accepted is False
    assert items[2].error is not None


def test_accepted_article_preserves_candidate_and_analysis() -> None:
    pipeline = _pipeline()
    with patch("app.pipeline.trend.ingest_rss", return_value=[ACCEPTED]):
        item = pipeline.run(FEED_URL)[0]

    assert item.candidate == ACCEPTED
    assert item.analysis is not None
    assert item.analysis.category == "Agentic AI"
    assert item.decision is not None
    assert item.decision.accepted is True
    assert item.error is None


def test_low_relevance_article_is_rejected() -> None:
    pipeline = _pipeline()
    with patch("app.pipeline.trend.ingest_rss", return_value=[REJECTED]):
        item = pipeline.run(FEED_URL)[0]

    assert item.candidate == REJECTED
    assert item.analysis is not None
    assert item.analysis.relevance_score == 0.2
    assert item.decision is not None
    assert item.decision.accepted is False
    assert item.decision.reason == "Relevance score below threshold"
    assert item.error is None


def test_trend_agent_failure_does_not_erase_neighbors() -> None:
    pipeline = _pipeline()
    with patch(
        "app.pipeline.trend.ingest_rss",
        return_value=[ACCEPTED, FAILED, REJECTED],
    ):
        items = pipeline.run(FEED_URL)

    assert items[0].decision is not None and items[0].decision.accepted is True
    assert items[1].error == "LLM output is not valid JSON"
    assert items[1].analysis is None
    assert items[1].decision is None
    assert items[2].decision is not None and items[2].decision.accepted is False


def test_llm_client_error_does_not_erase_neighbors() -> None:
    class MixedLlmClient:
        def complete(self, prompt: str) -> str:
            if FAILED.canonical_url in prompt:
                raise LlmClientError("LiteLLM completion failed for model test")
            if ACCEPTED.canonical_url in prompt:
                return ACCEPTED_JSON
            if REJECTED.canonical_url in prompt:
                return REJECTED_JSON
            raise AssertionError(f"no LLM fixture for prompt: {prompt}")

    items = TrendPipeline(
        llm=MixedLlmClient(),
        quality_gate=QualityGate(),
    ).process_candidates([ACCEPTED, FAILED, REJECTED])

    assert items[0].decision is not None and items[0].decision.accepted is True
    assert items[1].error == "LiteLLM completion failed for model test"
    assert items[1].analysis is None
    assert items[1].decision is None
    assert items[2].decision is not None and items[2].decision.accepted is False


def test_feed_level_ingestion_failure_propagates() -> None:
    pipeline = _pipeline()
    with patch(
        "app.pipeline.trend.ingest_rss",
        side_effect=RssFetchError("Unparseable RSS feed"),
    ):
        with pytest.raises(RssFetchError, match="Unparseable RSS feed"):
            pipeline.run(FEED_URL)


def test_pipeline_uses_supplied_llm_client() -> None:
    llm = MappingLlmClient({ACCEPTED.canonical_url: ACCEPTED_JSON})
    pipeline = _pipeline(llm)
    with patch("app.pipeline.trend.ingest_rss", return_value=[ACCEPTED]):
        pipeline.run(FEED_URL)
    assert llm.complete_calls == 1


def test_same_inputs_produce_the_same_quality_decisions() -> None:
    pipeline = _pipeline()
    with patch(
        "app.pipeline.trend.ingest_rss",
        return_value=[ACCEPTED, REJECTED],
    ):
        first = pipeline.run(FEED_URL)
        second = pipeline.run(FEED_URL)
    assert [item.decision for item in first] == [item.decision for item in second]
