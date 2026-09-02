from datetime import UTC, datetime

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.models import ArticleCandidate, QualityDecision, TrendAnalysis
from app.pipeline.results import PipelineItem
from app.repositories import ArticleRepository

FEED_URL = "https://example.com/rss.xml"
CANONICAL_URL = "https://example.com/articles/agents"
PUBLISHED_AT = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> ArticleCandidate:
    payload: dict[str, object] = {
        "source_url": FEED_URL,
        "canonical_url": CANONICAL_URL,
        "title": "New agent tooling ships",
        "excerpt": "A lab released an open agent framework.",
        "published_at": PUBLISHED_AT,
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


def _accepted_item() -> PipelineItem:
    return PipelineItem(
        candidate=_candidate(),
        analysis=_analysis(),
        decision=QualityDecision(accepted=True, reason=None),
    )


def _rejected_item() -> PipelineItem:
    return PipelineItem(
        candidate=_candidate(),
        analysis=_analysis(relevance_score=0.2),
        decision=QualityDecision(
            accepted=False, reason="Relevance score below threshold"
        ),
    )


def _failed_item() -> PipelineItem:
    return PipelineItem(
        candidate=_candidate(),
        error="LLM output is not valid JSON",
    )


def test_articles_table_uses_postgres_types(postgres_engine: Engine) -> None:
    columns = {
        column["name"]: column
        for column in inspect(postgres_engine).get_columns("articles")
    }
    assert "UUID" in str(columns["id"]["type"]).upper()
    assert "JSON" in str(columns["key_points"]["type"]).upper()
    published_type = columns["published_at"]["type"]
    assert getattr(published_type, "timezone", False) is True
    unique_constraints = inspect(postgres_engine).get_unique_constraints("articles")
    unique_indexes = [
        tuple(index["column_names"])
        for index in inspect(postgres_engine).get_indexes("articles")
        if index["unique"]
    ]
    unique_names = {tuple(item["column_names"]) for item in unique_constraints}
    unique_names |= set(unique_indexes)
    assert ("canonical_url",) in unique_names


def test_accepted_pipeline_item_persists(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(_accepted_item())
    assert stored is not None
    assert stored.accepted is True
    assert stored.quality_reason is None


def test_rejected_pipeline_item_persists(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(_rejected_item())
    assert stored is not None
    assert stored.accepted is False
    assert stored.quality_reason == "Relevance score below threshold"


def test_article_candidate_fields_round_trip(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(_accepted_item())
    assert stored is not None
    assert stored.source_url == FEED_URL
    assert stored.canonical_url == CANONICAL_URL
    assert stored.title == "New agent tooling ships"
    assert stored.excerpt == "A lab released an open agent framework."
    assert stored.published_at == PUBLISHED_AT


def test_trend_analysis_and_key_points_round_trip(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(_accepted_item())
    assert stored is not None
    assert stored.summary.startswith("A new open agent framework")
    assert stored.category == "Agentic AI"
    assert stored.relevance_score == 0.82
    assert stored.key_points == [
        "Open framework released",
        "Aimed at enterprise workflows",
    ]


def test_quality_decision_round_trip(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    stored = repo.save_pipeline_item(_rejected_item())
    fetched = repo.get_by_canonical_url(CANONICAL_URL)
    assert fetched is not None
    assert fetched.accepted is False
    assert fetched.quality_reason == "Relevance score below threshold"
    assert stored is not None
    assert fetched.id == stored.id


def test_duplicate_canonical_url_updates_in_place(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    first = repo.save_pipeline_item(_accepted_item())
    assert first is not None
    updated_item = PipelineItem(
        candidate=_candidate(
            title="Updated title",
            excerpt="Updated excerpt",
            source_url="https://example.com/other-feed.xml",
        ),
        analysis=_analysis(
            summary="Updated summary",
            category="LLMs",
            relevance_score=0.4,
            key_points=["Only one point"],
        ),
        decision=QualityDecision(
            accepted=False, reason="Relevance score below threshold"
        ),
    )
    second = repo.save_pipeline_item(updated_item)
    assert second is not None
    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.title == "Updated title"
    assert second.excerpt == "Updated excerpt"
    assert second.source_url == "https://example.com/other-feed.xml"
    assert second.summary == "Updated summary"
    assert second.category == "LLMs"
    assert second.relevance_score == 0.4
    assert second.key_points == ["Only one point"]
    assert second.accepted is False
    assert second.quality_reason == "Relevance score below threshold"
    assert second.updated_at >= first.updated_at


def test_failed_pipeline_item_is_not_persisted(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    assert repo.save_pipeline_item(_failed_item()) is None
    assert repo.get_by_canonical_url(CANONICAL_URL) is None


def test_get_by_canonical_url_returns_stored_article(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    saved = repo.save_pipeline_item(_accepted_item())
    fetched = repo.get_by_canonical_url(CANONICAL_URL)
    assert saved is not None
    assert fetched == saved


def test_unknown_canonical_url_returns_none(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    assert repo.get_by_canonical_url("https://example.com/missing") is None


def test_get_by_canonical_urls_returns_empty_for_no_urls(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    assert repo.get_by_canonical_urls([]) == {}


def test_get_by_canonical_urls_returns_known_rows_only(db_session: Session) -> None:
    repo = ArticleRepository(db_session)
    saved = repo.save_pipeline_item(_accepted_item())
    assert saved is not None
    found = repo.get_by_canonical_urls([CANONICAL_URL, "https://example.com/missing"])
    assert list(found) == [CANONICAL_URL]
    assert found[CANONICAL_URL] == saved
