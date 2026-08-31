import json
from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.models import ArticleCandidate
from app.pipeline import FeedIngestion
from app.quality import QualityGate
from app.repositories import ArticleRepository

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

UPDATED_JSON = json.dumps(
    {
        "summary": "Updated summary after a second ingest.",
        "category": "LLMs",
        "relevance_score": 0.4,
        "key_points": ["Only one point"],
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


def _llm() -> MappingLlmClient:
    return MappingLlmClient(
        {
            ACCEPTED.canonical_url: ACCEPTED_JSON,
            REJECTED.canonical_url: REJECTED_JSON,
            FAILED.canonical_url: "not json",
        }
    )


def test_accepted_and_rejected_persist_failed_does_not(db_session: Session) -> None:
    with patch(
        "app.pipeline.feed.ingest_rss",
        return_value=[ACCEPTED, REJECTED, FAILED],
    ):
        results = FeedIngestion(_llm(), quality_gate=QualityGate()).run(
            FEED_URL,
            db_session,
        )

    repo = ArticleRepository(db_session)
    accepted = repo.get_by_canonical_url(ACCEPTED.canonical_url)
    rejected = repo.get_by_canonical_url(REJECTED.canonical_url)
    assert accepted is not None
    assert accepted.accepted is True
    assert rejected is not None
    assert rejected.accepted is False
    assert rejected.quality_reason == "Relevance score below threshold"
    assert repo.get_by_canonical_url(FAILED.canonical_url) is None
    assert results[2].stored is None
    assert results[2].item.error is not None


def test_feed_ingestion_does_not_commit(
    db_session: Session, postgres_engine: Engine
) -> None:
    with patch("app.pipeline.feed.ingest_rss", return_value=[ACCEPTED]):
        FeedIngestion(_llm(), quality_gate=QualityGate()).run(FEED_URL, db_session)

    assert (
        ArticleRepository(db_session).get_by_canonical_url(ACCEPTED.canonical_url)
        is not None
    )

    with Session(postgres_engine) as other:
        assert (
            ArticleRepository(other).get_by_canonical_url(ACCEPTED.canonical_url)
            is None
        )


def test_duplicate_canonical_url_updates_in_place(db_session: Session) -> None:
    first_llm = MappingLlmClient({ACCEPTED.canonical_url: ACCEPTED_JSON})
    with patch("app.pipeline.feed.ingest_rss", return_value=[ACCEPTED]):
        first = FeedIngestion(first_llm, quality_gate=QualityGate()).run(
            FEED_URL,
            db_session,
        )
    assert first[0].stored is not None

    updated_candidate = ACCEPTED.model_copy(
        update={"title": "Updated title", "excerpt": "Updated excerpt"}
    )
    second_llm = MappingLlmClient({ACCEPTED.canonical_url: UPDATED_JSON})
    with patch("app.pipeline.feed.ingest_rss", return_value=[updated_candidate]):
        second = FeedIngestion(second_llm, quality_gate=QualityGate()).run(
            FEED_URL,
            db_session,
        )
    stored = second[0].stored
    assert stored is not None
    assert stored.id == first[0].stored.id
    assert stored.title == "Updated title"
    assert stored.excerpt == "Updated excerpt"
    assert stored.summary == "Updated summary after a second ingest."
    assert stored.category == "LLMs"
    assert stored.relevance_score == 0.4
    assert stored.accepted is False
    assert stored.quality_reason == "Relevance score below threshold"
