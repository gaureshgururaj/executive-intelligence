import pytest

from app.domain.models import PaperCandidate, ResearchAnalysis
from app.quality import ResearchQualityGate

PAPER = PaperCandidate(
    arxiv_id="2401.00001",
    title="Mixture-of-experts routing improves tool use",
    abstract="The authors propose a routing method for multi-agent systems.",
    authors=["Ada Lovelace"],
    paper_url="http://arxiv.org/abs/2401.00001v1",
    categories=["cs.LG"],
)

ANALYSIS = ResearchAnalysis(
    summary="A routing method may cut failed tool calls in multi-agent systems.",
    category="Agentic AI",
    relevance_score=0.82,
    key_findings=["Routing reduced failed tool calls"],
    practical_implications=["Leaders can watch routing as a reliability lever"],
)


def test_relevant_paper_with_findings_is_accepted() -> None:
    decision = ResearchQualityGate().evaluate(PAPER, ANALYSIS)
    assert decision.accepted is True
    assert decision.reason is None


def test_score_exactly_at_threshold_is_accepted() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.5})
    decision = ResearchQualityGate(min_relevance_score=0.5).evaluate(PAPER, analysis)
    assert decision.accepted is True
    assert decision.reason is None


def test_score_below_threshold_is_rejected() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.49})
    decision = ResearchQualityGate().evaluate(PAPER, analysis)
    assert decision.accepted is False
    assert decision.reason == "Relevance score below threshold"


def test_custom_threshold_is_applied() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.7})
    accepted = ResearchQualityGate(min_relevance_score=0.6).evaluate(PAPER, analysis)
    rejected = ResearchQualityGate(min_relevance_score=0.8).evaluate(PAPER, analysis)
    assert accepted.accepted is True
    assert rejected.accepted is False
    assert rejected.reason == "Relevance score below threshold"


def test_empty_key_findings_are_rejected() -> None:
    analysis = ANALYSIS.model_copy(update={"key_findings": []})
    decision = ResearchQualityGate().evaluate(PAPER, analysis)
    assert decision.accepted is False
    assert decision.reason == "Analysis has no key findings"


def test_empty_practical_implications_alone_are_accepted() -> None:
    analysis = ANALYSIS.model_copy(update={"practical_implications": []})
    decision = ResearchQualityGate().evaluate(PAPER, analysis)
    assert decision.accepted is True
    assert decision.reason is None


def test_first_failed_rule_wins_when_multiple_could_fail() -> None:
    analysis = ANALYSIS.model_copy(update={"relevance_score": 0.1, "key_findings": []})
    decision = ResearchQualityGate().evaluate(PAPER, analysis)
    assert decision.accepted is False
    assert decision.reason == "Relevance score below threshold"


def test_same_inputs_return_the_same_decision() -> None:
    gate = ResearchQualityGate()
    first = gate.evaluate(PAPER, ANALYSIS)
    second = gate.evaluate(PAPER, ANALYSIS)
    assert first == second


def test_invalid_threshold_is_rejected() -> None:
    with pytest.raises(ValueError, match="min_relevance_score"):
        ResearchQualityGate(min_relevance_score=1.1)
