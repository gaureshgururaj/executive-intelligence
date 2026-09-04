import json
from datetime import UTC, datetime

import pytest

from app.agents import ResearchAgent, ResearchAgentError, build_research_prompt
from app.domain.models import PaperCandidate, ResearchAnalysis
from app.llm.errors import LlmClientError

PAPER = PaperCandidate(
    arxiv_id="2401.00001",
    title="Mixture-of-experts routing improves tool use",
    abstract=(
        "The authors propose a routing method that reduces failed tool calls "
        "in multi-agent systems."
    ),
    authors=["Ada Lovelace", "Alan Turing"],
    published_at=datetime(2026, 9, 1, tzinfo=UTC),
    updated_at=datetime(2026, 9, 2, tzinfo=UTC),
    paper_url="http://arxiv.org/abs/2401.00001v1",
    pdf_url="http://arxiv.org/pdf/2401.00001v1",
    categories=["cs.LG", "cs.AI"],
)

VALID_PAYLOAD = {
    "summary": "A routing method may cut failed tool calls in multi-agent systems.",
    "category": "Agentic AI",
    "relevance_score": 0.74,
    "key_findings": [
        "Routing reduced failed tool calls",
        "Evaluated in multi-agent systems",
    ],
    "practical_implications": [
        "Leaders can watch routing as a reliability lever",
    ],
}


class FakeLlmClient:
    def __init__(
        self,
        response: str | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_valid_json_returns_research_analysis() -> None:
    client = FakeLlmClient(json.dumps(VALID_PAYLOAD))
    result = ResearchAgent(client).analyze(PAPER)
    assert result == ResearchAnalysis.model_validate(VALID_PAYLOAD)
    assert result.category == "Agentic AI"
    assert result.relevance_score == 0.74
    assert result.key_findings == [
        "Routing reduced failed tool calls",
        "Evaluated in multi-agent systems",
    ]
    assert result.practical_implications == [
        "Leaders can watch routing as a reliability lever",
    ]


def test_empty_findings_and_implications_are_allowed() -> None:
    payload = {
        **VALID_PAYLOAD,
        "key_findings": [],
        "practical_implications": [],
    }
    client = FakeLlmClient(json.dumps(payload))
    result = ResearchAgent(client).analyze(PAPER)
    assert result.key_findings == []
    assert result.practical_implications == []


def test_prompt_includes_paper_fields_and_omits_urls() -> None:
    client = FakeLlmClient(json.dumps(VALID_PAYLOAD))
    ResearchAgent(client).analyze(PAPER)
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "Mixture-of-experts routing improves tool use" in prompt
    assert "reduces failed tool calls" in prompt
    assert "Ada Lovelace" in prompt
    assert "Alan Turing" in prompt
    assert "cs.LG" in prompt
    assert "cs.AI" in prompt
    assert PAPER.published_at is not None
    assert PAPER.updated_at is not None
    assert PAPER.published_at.isoformat() in prompt
    assert PAPER.updated_at.isoformat() in prompt
    assert PAPER.arxiv_id not in prompt
    assert PAPER.paper_url not in prompt
    assert PAPER.pdf_url is not None
    assert PAPER.pdf_url not in prompt
    assert prompt == build_research_prompt(PAPER)


def test_missing_dates_and_categories_are_rendered_as_none() -> None:
    paper = PaperCandidate(
        arxiv_id="2401.00002",
        title="Untitled methods paper",
        abstract="A short abstract about evaluation protocol design.",
        authors=["Grace Hopper"],
        paper_url="http://arxiv.org/abs/2401.00002v1",
    )
    prompt = build_research_prompt(paper)
    assert "Categories: (none)" in prompt
    assert "Published: (none)" in prompt
    assert "Updated: (none)" in prompt


@pytest.mark.parametrize("score", [0.0, 1.0])
def test_relevance_score_boundaries_are_accepted(score: float) -> None:
    payload = {**VALID_PAYLOAD, "relevance_score": score}
    result = ResearchAgent(FakeLlmClient(json.dumps(payload))).analyze(PAPER)
    assert result.relevance_score == score


def test_malformed_json_raises_research_agent_error() -> None:
    client = FakeLlmClient("not json")
    with pytest.raises(ResearchAgentError, match="not valid JSON"):
        ResearchAgent(client).analyze(PAPER)


def test_prose_around_json_raises_research_agent_error() -> None:
    wrapped = "Here is the result:\n" + json.dumps(VALID_PAYLOAD)
    client = FakeLlmClient(wrapped)
    with pytest.raises(ResearchAgentError, match="not valid JSON"):
        ResearchAgent(client).analyze(PAPER)


def test_missing_required_fields_raises_research_agent_error() -> None:
    client = FakeLlmClient(json.dumps({"summary": "Only a summary"}))
    with pytest.raises(ResearchAgentError, match="ResearchAnalysis validation"):
        ResearchAgent(client).analyze(PAPER)


def test_relevance_score_out_of_range_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "relevance_score": 1.4}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(ResearchAgentError, match="ResearchAnalysis validation"):
        ResearchAgent(client).analyze(PAPER)


def test_blank_summary_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "summary": "   "}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(ResearchAgentError, match="ResearchAnalysis validation"):
        ResearchAgent(client).analyze(PAPER)


def test_blank_category_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "category": ""}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(ResearchAgentError, match="ResearchAnalysis validation"):
        ResearchAgent(client).analyze(PAPER)


def test_blank_key_finding_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "key_findings": ["A finding", "  "]}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(ResearchAgentError, match="ResearchAnalysis validation"):
        ResearchAgent(client).analyze(PAPER)


def test_blank_practical_implication_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "practical_implications": [""]}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(ResearchAgentError, match="ResearchAnalysis validation"):
        ResearchAgent(client).analyze(PAPER)


def test_llm_client_error_propagates() -> None:
    client = FakeLlmClient(error=LlmClientError("provider timeout"))
    with pytest.raises(LlmClientError, match="provider timeout"):
        ResearchAgent(client).analyze(PAPER)
