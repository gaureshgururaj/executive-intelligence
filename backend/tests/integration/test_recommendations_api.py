from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.models import (
    ArticleCandidate,
    PaperCandidate,
    QualityDecision,
    RecommendationProfile,
    ResearchAnalysis,
    TrendAnalysis,
)
from app.main import app
from app.pipeline.results import PipelineItem
from app.repositories import (
    ArticleRepository,
    PaperRepository,
    RecommendationProfileRepository,
    StoredRecommendationProfile,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
FEED_URL = "https://example.com/rss.xml"
PROFILE_FIELDS = {"id", "name", "interests"}
ARTICLE_ITEM_FIELDS = {
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
PAPER_ITEM_FIELDS = {
    "id",
    "arxiv_id",
    "title",
    "abstract",
    "authors",
    "published_at",
    "arxiv_updated_at",
    "paper_url",
    "pdf_url",
    "categories",
    "summary",
    "category",
    "relevance_score",
    "key_findings",
    "practical_implications",
    "created_at",
}
RECOMMENDATION_FIELDS = {
    "content_type",
    "recommendation_score",
    "matched_interests",
    "reason",
    "item",
}


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _save_profile(
    session: Session, *, name: str, interests: list[str]
) -> StoredRecommendationProfile:
    return RecommendationProfileRepository(session).save(
        RecommendationProfile(id=UUID(int=1), name=name, interests=interests)
    )


def _article_item(
    *,
    accepted: bool,
    canonical_url: str,
    title: str,
    summary: str,
    category: str,
    key_points: list[str],
    relevance_score: float = 0.9,
) -> PipelineItem:
    reason = None if accepted else "Relevance score below threshold"
    return PipelineItem(
        candidate=ArticleCandidate(
            source_url=FEED_URL,
            canonical_url=canonical_url,
            title=title,
            excerpt="Enough text for publication.",
            published_at=NOW,
        ),
        analysis=TrendAnalysis(
            summary=summary,
            category=category,
            relevance_score=relevance_score,
            key_points=key_points,
        ),
        decision=QualityDecision(accepted=accepted, reason=reason),
    )


def _paper(
    *,
    accepted: bool,
    arxiv_id: str,
    title: str,
    summary: str,
    category: str,
    key_findings: list[str],
    relevance_score: float = 0.4,
) -> tuple[PaperCandidate, ResearchAnalysis, QualityDecision]:
    reason = None if accepted else "Relevance score below threshold"
    return (
        PaperCandidate(
            arxiv_id=arxiv_id,
            title=title,
            abstract="UNIQUE_ABSTRACT_TOKEN_SHOULD_NOT_APPEAR",
            authors=["Ada Lovelace"],
            published_at=NOW,
            paper_url=f"http://arxiv.org/abs/{arxiv_id}",
            categories=["cs.ZZ"],
        ),
        ResearchAnalysis(
            summary=summary,
            category=category,
            relevance_score=relevance_score,
            key_findings=key_findings,
            practical_implications=["Leaders can watch the finding"],
        ),
        QualityDecision(accepted=accepted, reason=reason),
    )


def test_profiles_endpoint_returns_empty_list(
    db_session: Session, api_client: TestClient
) -> None:
    response = api_client.get("/api/v1/recommendation-profiles")
    assert response.status_code == 200
    assert response.json() == []


def test_profiles_endpoint_returns_public_fields_in_name_order(
    db_session: Session, api_client: TestClient
) -> None:
    _save_profile(db_session, name="Zebra", interests=["planning"])
    _save_profile(db_session, name="Alpha", interests=["GPT", "licensing"])
    response = api_client.get("/api/v1/recommendation-profiles")
    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload] == ["Alpha", "Zebra"]
    assert payload[0]["interests"] == ["GPT", "licensing"]
    assert set(payload[0].keys()) == PROFILE_FIELDS
    assert "created_at" not in payload[0]
    assert "updated_at" not in payload[0]


def test_missing_profile_returns_404(
    db_session: Session, api_client: TestClient
) -> None:
    missing = "00000000-0000-0000-0000-000000000099"
    response = api_client.get(f"/api/v1/recommendations?profile_id={missing}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Recommendation profile not found"


def test_malformed_profile_id_returns_422(
    db_session: Session, api_client: TestClient
) -> None:
    response = api_client.get("/api/v1/recommendations?profile_id=not-a-uuid")
    assert response.status_code == 422


def test_valid_profile_with_no_matches_returns_empty_list(
    db_session: Session, api_client: TestClient
) -> None:
    ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=True,
            canonical_url="https://example.com/articles/agents",
            title="Agent framework ships",
            summary="A new agent framework.",
            category="Agentic AI",
            key_points=["Open framework released"],
        )
    )
    profile = _save_profile(
        db_session, name="Unrelated", interests=["quantum annealing"]
    )
    response = api_client.get(f"/api/v1/recommendations?profile_id={profile.id}")
    assert response.status_code == 200
    assert response.json() == []


def test_article_and_paper_recommendations_use_public_item_shapes(
    db_session: Session, api_client: TestClient
) -> None:
    article = ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=True,
            canonical_url="https://example.com/articles/gpt",
            title="GPT document review",
            summary="GPT-6 reviewed documents.",
            category="Enterprise AI Applications",
            key_points=["GPT-6 Astra enabled review"],
            relevance_score=0.95,
        )
    )
    paper = PaperRepository(db_session).save(
        *_paper(
            accepted=True,
            arxiv_id="2401.00001",
            title="Speech enhancement method",
            summary="A speech enhancement method using codecs.",
            category="Speech Enhancement",
            key_findings=["Continuous representations help"],
            relevance_score=0.4,
        )
    )
    assert article is not None
    assert paper is not None
    profile = _save_profile(
        db_session, name="Mixed", interests=["GPT", "speech enhancement"]
    )
    response = api_client.get(f"/api/v1/recommendations?profile_id={profile.id}")
    assert response.status_code == 200
    payload = response.json()
    assert [item["content_type"] for item in payload] == ["article", "paper"]
    article_item = payload[0]
    paper_item = payload[1]
    assert set(article_item.keys()) == RECOMMENDATION_FIELDS
    assert set(paper_item.keys()) == RECOMMENDATION_FIELDS
    assert article_item["matched_interests"] == ["GPT"]
    assert article_item["reason"] == "Matches your interest in GPT"
    assert isinstance(article_item["recommendation_score"], float)
    assert set(article_item["item"].keys()) == ARTICLE_ITEM_FIELDS
    assert article_item["item"]["title"] == "GPT document review"
    assert "accepted" not in article_item["item"]
    assert paper_item["matched_interests"] == ["speech enhancement"]
    assert paper_item["reason"] == "Matches your interest in speech enhancement"
    assert set(paper_item["item"].keys()) == PAPER_ITEM_FIELDS
    assert paper_item["item"]["title"] == "Speech enhancement method"
    assert paper_item["item"]["abstract"] == "UNIQUE_ABSTRACT_TOKEN_SHOULD_NOT_APPEAR"
    assert "accepted" not in paper_item["item"]


def test_rejected_content_is_omitted_from_recommendations(
    db_session: Session, api_client: TestClient
) -> None:
    ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=False,
            canonical_url="https://example.com/articles/rejected",
            title="Rejected GPT",
            summary="Rejected GPT news.",
            category="Enterprise AI Applications",
            key_points=["GPT should not appear"],
            relevance_score=0.2,
        )
    )
    PaperRepository(db_session).save(
        *_paper(
            accepted=False,
            arxiv_id="2401.00002",
            title="Rejected speech paper",
            summary="Rejected speech enhancement work.",
            category="Speech Enhancement",
            key_findings=["Speech should not appear"],
            relevance_score=0.2,
        )
    )
    profile = _save_profile(
        db_session, name="Mixed", interests=["GPT", "speech enhancement"]
    )
    updated_before = profile.updated_at
    response = api_client.get(f"/api/v1/recommendations?profile_id={profile.id}")
    assert response.status_code == 200
    assert response.json() == []
    fetched = RecommendationProfileRepository(db_session).get_by_id(profile.id)
    assert fetched is not None
    assert fetched.updated_at == updated_before
    assert len(RecommendationProfileRepository(db_session).list_all()) == 1
