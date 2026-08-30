from datetime import UTC, datetime

import pytest

from app.domain.models import ArticleCandidate, TrendAnalysis
from app.quality import QualityGate

CANDIDATE = ArticleCandidate(
    source_url="https://example.com/rss.xml",
    canonical_url="https://example.com/articles/agents",
    title="New agent tooling ships",
    excerpt="A lab released an open agent framework for enterprise workflows.",
    published_at=datetime(2026, 8, 30, tzinfo=UTC),
)

ANALYSIS = TrendAnalysis(
    summary="A new open agent framework may speed enterprise automation.",
    category="Agentic AI",
    relevance_score=0.82,
    key_points=["Open framework released", "Aimed at enterprise workflows"],
)


def test_valid_relevant_article_is_accepted() -> None:
    decision = QualityGate().evaluate(CANDIDATE, ANALYSIS)
    assert decision.accepted is True
    assert decision.reason is None


def test_score_exactly_at_threshold_is_accepted() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.5})
    decision = QualityGate(min_relevance_score=0.5).evaluate(CANDIDATE, analysis)
    assert decision.accepted is True


def test_score_below_threshold_is_rejected() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.49})
    decision = QualityGate().evaluate(CANDIDATE, analysis)
    assert decision.accepted is False
    assert decision.reason == "Relevance score below threshold"


def test_custom_threshold_is_applied() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.7})
    accepted = QualityGate(min_relevance_score=0.6).evaluate(CANDIDATE, analysis)
    rejected = QualityGate(min_relevance_score=0.8).evaluate(CANDIDATE, analysis)
    assert accepted.accepted is True
    assert rejected.accepted is False
    assert rejected.reason == "Relevance score below threshold"


def test_missing_excerpt_is_accepted_when_key_points_exist() -> None:
    candidate = CANDIDATE.model_copy(update={"excerpt": None})
    decision = QualityGate().evaluate(candidate, ANALYSIS)
    assert decision.accepted is True
    assert decision.reason is None


def test_insufficient_usable_content_is_rejected() -> None:
    candidate = CANDIDATE.model_copy(update={"excerpt": None})
    analysis = ANALYSIS.model_copy(update={"key_points": []})
    decision = QualityGate().evaluate(candidate, analysis)
    assert decision.accepted is False
    assert decision.reason == "Insufficient usable content"


def test_empty_key_points_with_excerpt_is_rejected() -> None:
    analysis = ANALYSIS.model_copy(update={"key_points": []})
    decision = QualityGate().evaluate(CANDIDATE, analysis)
    assert decision.accepted is False
    assert decision.reason == "Analysis has no key points"


def test_first_failed_rule_wins_when_multiple_could_fail() -> None:
    candidate = CANDIDATE.model_copy(update={"excerpt": None})
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.1, "key_points": []})
    decision = QualityGate().evaluate(candidate, analysis)
    assert decision.accepted is False
    assert decision.reason == "Relevance score below threshold"


def test_same_inputs_return_the_same_decision() -> None:
    gate = QualityGate()
    first = gate.evaluate(CANDIDATE, ANALYSIS)
    second = gate.evaluate(CANDIDATE, ANALYSIS)
    assert first == second


def test_invalid_threshold_is_rejected() -> None:
    with pytest.raises(ValueError, match="min_relevance_score"):
        QualityGate(min_relevance_score=1.1)
