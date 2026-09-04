import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.domain.models import (
    ArticleCandidate,
    PaperCandidate,
    QualityDecision,
    RecommendationProfile,
    ResearchAnalysis,
    TrendAnalysis,
)
from app.pipeline.results import PipelineItem
from app.recommendations.errors import RecommendationProfileNotFoundError
from app.recommendations.service import RecommendationService
from app.repositories import (
    ArticleRepository,
    PaperRepository,
    RecommendationProfileRepository,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
FEED_URL = "https://example.com/rss.xml"


def _article_item(
    *,
    accepted: bool,
    canonical_url: str,
    title: str,
    summary: str,
    category: str,
    key_points: list[str],
    relevance_score: float = 0.8,
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
    relevance_score: float = 0.7,
) -> tuple[PaperCandidate, ResearchAnalysis, QualityDecision]:
    reason = None if accepted else "Relevance score below threshold"
    candidate = PaperCandidate(
        arxiv_id=arxiv_id,
        title=title,
        abstract="UNIQUE_ABSTRACT_TOKEN_SHOULD_NOT_APPEAR",
        authors=["Ada Lovelace"],
        published_at=NOW,
        paper_url=f"http://arxiv.org/abs/{arxiv_id}",
        categories=["cs.ZZ"],
    )
    analysis = ResearchAnalysis(
        summary=summary,
        category=category,
        relevance_score=relevance_score,
        key_findings=key_findings,
        practical_implications=["Leaders can watch the finding"],
    )
    decision = QualityDecision(accepted=accepted, reason=reason)
    return candidate, analysis, decision


def _save_profile(
    session: Session,
    *,
    name: str,
    interests: list[str],
) -> uuid.UUID:
    stored = RecommendationProfileRepository(session).save(
        RecommendationProfile(
            id=uuid.uuid4(),
            name=name,
            interests=interests,
        )
    )
    return stored.id


def test_accepted_article_and_paper_participate(db_session: Session) -> None:
    ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=True,
            canonical_url="https://example.com/articles/agents",
            title="Agent framework ships",
            summary="A new agent framework may speed automation.",
            category="Agentic AI",
            key_points=["Open framework released"],
        )
    )
    PaperRepository(db_session).save(
        *_paper(
            accepted=True,
            arxiv_id="2401.00001",
            title="Speech enhancement method",
            summary="A speech enhancement method using codecs.",
            category="Speech Enhancement",
            key_findings=["Continuous representations help"],
        )
    )
    profile_id = _save_profile(
        db_session,
        name="Mixed",
        interests=["agent", "speech enhancement"],
    )
    results = RecommendationService(db_session).recommend_for_profile(
        profile_id, now=NOW
    )
    types = {item.content_type for item in results}
    assert types == {"article", "paper"}


def test_rejected_article_is_excluded(db_session: Session) -> None:
    ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=True,
            canonical_url="https://example.com/articles/accepted",
            title="Accepted agents",
            summary="Accepted agent tooling.",
            category="Agentic AI",
            key_points=["Agents shipped"],
        )
    )
    ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=False,
            canonical_url="https://example.com/articles/rejected",
            title="Rejected quantum",
            summary="Rejected quantum computing news.",
            category="Quantum",
            key_points=["Quantum annealing"],
            relevance_score=0.2,
        )
    )
    profile_id = _save_profile(
        db_session, name="Quantum watcher", interests=["quantum"]
    )
    results = RecommendationService(db_session).recommend_for_profile(
        profile_id, now=NOW
    )
    assert results == []


def test_rejected_paper_is_excluded(db_session: Session) -> None:
    PaperRepository(db_session).save(
        *_paper(
            accepted=True,
            arxiv_id="2401.00001",
            title="Accepted speech paper",
            summary="Accepted speech enhancement work.",
            category="Speech Enhancement",
            key_findings=["Codecs help"],
        )
    )
    PaperRepository(db_session).save(
        *_paper(
            accepted=False,
            arxiv_id="2401.00002",
            title="Rejected planning paper",
            summary="Rejected hierarchical planning work.",
            category="Automated Planning",
            key_findings=["Planning encodings"],
            relevance_score=0.2,
        )
    )
    profile_id = _save_profile(db_session, name="Planning", interests=["planning"])
    results = RecommendationService(db_session).recommend_for_profile(
        profile_id, now=NOW
    )
    assert results == []


def test_missing_profile_raises(db_session: Session) -> None:
    missing = uuid.UUID("00000000-0000-0000-0000-000000000099")
    with pytest.raises(RecommendationProfileNotFoundError) as exc:
        RecommendationService(db_session).recommend_for_profile(missing, now=NOW)
    assert exc.value.profile_id == missing


def test_valid_profile_with_no_matches_returns_empty(db_session: Session) -> None:
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
    profile_id = _save_profile(
        db_session, name="Unrelated", interests=["quantum annealing"]
    )
    assert (
        RecommendationService(db_session).recommend_for_profile(profile_id, now=NOW)
        == []
    )


def test_empty_interests_return_empty(db_session: Session) -> None:
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
    profile_id = _save_profile(db_session, name="Empty", interests=[])
    assert (
        RecommendationService(db_session).recommend_for_profile(profile_id, now=NOW)
        == []
    )


def test_supplied_now_is_deterministic(db_session: Session) -> None:
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
    profile_id = _save_profile(db_session, name="Agents", interests=["agent"])
    service = RecommendationService(db_session)
    first = service.recommend_for_profile(profile_id, now=NOW)
    second = service.recommend_for_profile(profile_id, now=NOW)
    later = service.recommend_for_profile(profile_id, now=NOW + timedelta(days=20))
    assert first == second
    assert first != later


def test_two_profiles_rank_the_same_corpus_differently(db_session: Session) -> None:
    ArticleRepository(db_session).save_pipeline_item(
        _article_item(
            accepted=True,
            canonical_url="https://example.com/articles/gpt",
            title="GPT document review",
            summary="GPT-6 reviewed documents.",
            category="Enterprise AI Applications",
            key_points=["GPT-6 Astra enabled review"],
            relevance_score=0.9,
        )
    )
    PaperRepository(db_session).save(
        *_paper(
            accepted=True,
            arxiv_id="2401.00001",
            title="Speech enhancement method",
            summary="A speech enhancement method using codecs.",
            category="Speech Enhancement",
            key_findings=["Continuous representations help"],
            relevance_score=0.9,
        )
    )
    strategy_id = _save_profile(db_session, name="Strategy", interests=["GPT"])
    research_id = _save_profile(
        db_session, name="Research", interests=["speech enhancement"]
    )
    service = RecommendationService(db_session)
    strategy = service.recommend_for_profile(strategy_id, now=NOW)
    research = service.recommend_for_profile(research_id, now=NOW)
    assert [item.content_type for item in strategy] == ["article"]
    assert [item.content_type for item in research] == ["paper"]


def test_recommend_for_profile_does_not_commit(db_session: Session) -> None:
    db_session.commit = MagicMock()
    profile_id = _save_profile(db_session, name="Empty", interests=[])
    RecommendationService(db_session).recommend_for_profile(profile_id, now=NOW)
    db_session.commit.assert_not_called()
