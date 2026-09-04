from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.models import (
    ArticleCandidate,
    PaperCandidate,
    QualityDecision,
    ResearchAnalysis,
    TrendAnalysis,
)

VALID_URL = "https://example.com/article"


def test_article_candidate_accepts_valid_payload() -> None:
    candidate = ArticleCandidate(
        source_url=VALID_URL,
        canonical_url="https://example.com/article?utm=1",
        title="  New model release  ",
        excerpt="  A short excerpt.  ",
        published_at=datetime(2026, 8, 30, tzinfo=UTC),
    )
    assert candidate.title == "New model release"
    assert candidate.excerpt == "A short excerpt."
    assert candidate.source_url.startswith("https://")


def test_article_candidate_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        ArticleCandidate(
            source_url=VALID_URL,
            canonical_url=VALID_URL,
            title="   ",
        )


def test_article_candidate_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        ArticleCandidate(
            source_url="not-a-url",
            canonical_url=VALID_URL,
            title="Valid title",
        )


def test_trend_analysis_rejects_relevance_score_out_of_range() -> None:
    with pytest.raises(ValidationError):
        TrendAnalysis(
            summary="Executives should watch agent tooling.",
            category="agentic_ai",
            relevance_score=1.2,
            key_points=["Point one"],
        )


def test_trend_analysis_rejects_blank_key_points() -> None:
    with pytest.raises(ValidationError):
        TrendAnalysis(
            summary="Executives should watch agent tooling.",
            category="agentic_ai",
            relevance_score=0.8,
            key_points=["Point one", "  "],
        )


def test_quality_decision_requires_reason_when_rejected() -> None:
    with pytest.raises(ValidationError):
        QualityDecision(accepted=False, reason=None)


def test_quality_decision_accepts_rejection_with_reason() -> None:
    decision = QualityDecision(accepted=False, reason="duplicate")
    assert decision.accepted is False
    assert decision.reason == "duplicate"


def test_paper_candidate_accepts_valid_payload() -> None:
    paper = PaperCandidate(
        arxiv_id="  2401.00001  ",
        title="  Large\nLanguage  Models  ",
        abstract="  An abstract\nwith space.  ",
        authors=["  Ada Lovelace  ", "  "],
        paper_url="http://arxiv.org/abs/2401.00001v1",
        pdf_url="http://arxiv.org/pdf/2401.00001v1",
        categories=["  cs.LG  ", "   "],
    )
    assert paper.arxiv_id == "2401.00001"
    assert paper.title == "Large Language Models"
    assert paper.abstract == "An abstract with space."
    assert paper.authors == ["Ada Lovelace"]
    assert paper.categories == ["cs.LG"]
    assert paper.pdf_url == "http://arxiv.org/pdf/2401.00001v1"


def test_paper_candidate_allows_missing_pdf_url() -> None:
    paper = PaperCandidate(
        arxiv_id="2401.00001",
        title="Title",
        abstract="Abstract",
        authors=["Ada Lovelace"],
        paper_url="http://arxiv.org/abs/2401.00001",
        pdf_url=None,
    )
    assert paper.pdf_url is None


def test_paper_candidate_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        PaperCandidate(
            arxiv_id="2401.00001",
            title="   ",
            abstract="Abstract",
            authors=["Ada Lovelace"],
            paper_url="http://arxiv.org/abs/2401.00001",
        )


def test_paper_candidate_rejects_blank_arxiv_id() -> None:
    with pytest.raises(ValidationError):
        PaperCandidate(
            arxiv_id="   ",
            title="Title",
            abstract="Abstract",
            authors=["Ada Lovelace"],
            paper_url="http://arxiv.org/abs/2401.00001",
        )


def test_paper_candidate_rejects_empty_authors() -> None:
    with pytest.raises(ValidationError):
        PaperCandidate(
            arxiv_id="2401.00001",
            title="Title",
            abstract="Abstract",
            authors=["  "],
            paper_url="http://arxiv.org/abs/2401.00001",
        )


def test_paper_candidate_rejects_invalid_paper_url() -> None:
    with pytest.raises(ValidationError):
        PaperCandidate(
            arxiv_id="2401.00001",
            title="Title",
            abstract="Abstract",
            authors=["Ada Lovelace"],
            paper_url="not-a-url",
        )


def test_research_analysis_accepts_empty_lists() -> None:
    analysis = ResearchAnalysis(
        summary="A routing method may cut failed tool calls.",
        category="Agentic AI",
        relevance_score=0.5,
        key_findings=[],
        practical_implications=[],
    )
    assert analysis.key_findings == []
    assert analysis.practical_implications == []


def test_research_analysis_rejects_relevance_score_out_of_range() -> None:
    with pytest.raises(ValidationError):
        ResearchAnalysis(
            summary="A routing method may cut failed tool calls.",
            category="Agentic AI",
            relevance_score=1.2,
            key_findings=["Point one"],
        )


def test_research_analysis_rejects_blank_key_findings() -> None:
    with pytest.raises(ValidationError):
        ResearchAnalysis(
            summary="A routing method may cut failed tool calls.",
            category="Agentic AI",
            relevance_score=0.8,
            key_findings=["Point one", "  "],
        )


def test_research_analysis_rejects_blank_practical_implications() -> None:
    with pytest.raises(ValidationError):
        ResearchAnalysis(
            summary="A routing method may cut failed tool calls.",
            category="Agentic AI",
            relevance_score=0.8,
            practical_implications=["  "],
        )


def test_research_analysis_rejects_blank_summary() -> None:
    with pytest.raises(ValidationError):
        ResearchAnalysis(
            summary="   ",
            category="Agentic AI",
            relevance_score=0.8,
        )
