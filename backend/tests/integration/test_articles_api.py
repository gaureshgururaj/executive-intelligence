from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.models import ArticleCandidate, QualityDecision, TrendAnalysis
from app.main import app
from app.pipeline.results import PipelineItem
from app.repositories import ArticleRepository

FEED_URL = "https://example.com/rss.xml"
RESPONSE_FIELDS = {
    "id",
    "canonical_url",
    "title",
    "excerpt",
    "published_at",
    "summary",
    "category",
    "relevance_score",
    "key_points",
    "created_at",
}


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _candidate(**overrides: object) -> ArticleCandidate:
    payload: dict[str, object] = {
        "source_url": FEED_URL,
        "canonical_url": "https://example.com/articles/accepted",
        "title": "Accepted article",
        "excerpt": "Enough text for publication.",
        "published_at": datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    }
    payload.update(overrides)
    return ArticleCandidate.model_validate(payload)


def _analysis(**overrides: object) -> TrendAnalysis:
    payload: dict[str, object] = {
        "summary": "A new open agent framework may speed enterprise automation.",
        "category": "Agentic AI",
        "relevance_score": 0.82,
        "key_points": ["Open framework released", "Aimed at enterprise workflows"],
    }
    payload.update(overrides)
    return TrendAnalysis.model_validate(payload)


def _item(
    *,
    accepted: bool,
    canonical_url: str,
    title: str,
    published_at: datetime | None,
    relevance_score: float = 0.82,
) -> PipelineItem:
    reason = None if accepted else "Relevance score below threshold"
    return PipelineItem(
        candidate=_candidate(
            canonical_url=canonical_url,
            title=title,
            published_at=published_at,
        ),
        analysis=_analysis(relevance_score=relevance_score),
        decision=QualityDecision(accepted=accepted, reason=reason),
    )


def test_articles_endpoint_returns_empty_list(
    db_session: Session, api_client: TestClient
) -> None:
    response = api_client.get("/api/v1/articles")
    assert response.status_code == 200
    assert response.json() == []


def test_accepted_article_appears_in_feed(
    db_session: Session, api_client: TestClient
) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(
        _item(
            accepted=True,
            canonical_url="https://example.com/articles/accepted",
            title="Accepted article",
            published_at=datetime(2026, 8, 30, tzinfo=UTC),
        )
    )
    assert stored is not None
    response = api_client.get("/api/v1/articles")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    item = payload[0]
    assert set(item.keys()) == RESPONSE_FIELDS
    assert item["title"] == "Accepted article"
    assert item["canonical_url"] == "https://example.com/articles/accepted"
    assert item["summary"].startswith("A new open agent framework")
    assert item["category"] == "Agentic AI"
    assert item["relevance_score"] == 0.82
    assert item["key_points"] == [
        "Open framework released",
        "Aimed at enterprise workflows",
    ]
    assert UUID(item["id"]) == stored.id
    assert item["published_at"].startswith("2026-08-30")
    assert item["created_at"]
    assert "accepted" not in item
    assert "quality_reason" not in item
    assert "updated_at" not in item


def test_rejected_article_does_not_appear(
    db_session: Session, api_client: TestClient
) -> None:
    repo = ArticleRepository(db_session)
    repo.save_pipeline_item(
        _item(
            accepted=True,
            canonical_url="https://example.com/articles/accepted",
            title="Accepted article",
            published_at=datetime(2026, 8, 30, tzinfo=UTC),
        )
    )
    repo.save_pipeline_item(
        _item(
            accepted=False,
            canonical_url="https://example.com/articles/rejected",
            title="Rejected article",
            published_at=datetime(2026, 8, 31, tzinfo=UTC),
            relevance_score=0.2,
        )
    )
    response = api_client.get("/api/v1/articles")
    titles = [item["title"] for item in response.json()]
    assert titles == ["Accepted article"]
    rejected = repo.get_by_canonical_url("https://example.com/articles/rejected")
    assert rejected is not None


def test_accepted_articles_are_ordered_by_published_at(
    db_session: Session, api_client: TestClient
) -> None:
    repo = ArticleRepository(db_session)
    repo.save_pipeline_item(
        _item(
            accepted=True,
            canonical_url="https://example.com/articles/older",
            title="Older",
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
    )
    repo.save_pipeline_item(
        _item(
            accepted=True,
            canonical_url="https://example.com/articles/undated",
            title="Undated",
            published_at=None,
        )
    )
    repo.save_pipeline_item(
        _item(
            accepted=True,
            canonical_url="https://example.com/articles/newer",
            title="Newer",
            published_at=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=29),
        )
    )
    response = api_client.get("/api/v1/articles")
    assert [item["title"] for item in response.json()] == ["Newer", "Older", "Undated"]


def test_list_articles_is_read_only(
    db_session: Session, api_client: TestClient
) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(
        _item(
            accepted=True,
            canonical_url="https://example.com/articles/accepted",
            title="Accepted article",
            published_at=datetime(2026, 8, 30, tzinfo=UTC),
        )
    )
    assert stored is not None
    updated_before = stored.updated_at
    api_client.get("/api/v1/articles")
    fetched = repo.get_by_canonical_url("https://example.com/articles/accepted")
    assert fetched is not None
    assert fetched.updated_at == updated_before
    assert fetched.title == stored.title
