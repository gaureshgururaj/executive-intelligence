import json
from datetime import UTC, datetime

import pytest

from app.agents import TrendAgent, TrendAgentError, build_trend_prompt
from app.domain.models import ArticleCandidate, TrendAnalysis

CANDIDATE = ArticleCandidate(
    source_url="https://example.com/rss.xml",
    canonical_url="https://example.com/articles/agents",
    title="New agent tooling ships",
    excerpt="A lab released an open agent framework for enterprise workflows.",
    published_at=datetime(2026, 8, 30, tzinfo=UTC),
)

VALID_PAYLOAD = {
    "summary": "A new open agent framework may speed enterprise automation.",
    "category": "Agentic AI",
    "relevance_score": 0.82,
    "key_points": [
        "Open framework released",
        "Aimed at enterprise workflows",
    ],
}


class FakeLlmClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_valid_json_returns_trend_analysis() -> None:
    client = FakeLlmClient(json.dumps(VALID_PAYLOAD))
    result = TrendAgent(client).analyze(CANDIDATE)
    assert result == TrendAnalysis.model_validate(VALID_PAYLOAD)
    assert result.category == "Agentic AI"
    assert result.relevance_score == 0.82
    assert result.key_points == [
        "Open framework released",
        "Aimed at enterprise workflows",
    ]


def test_prompt_includes_candidate_title_and_excerpt() -> None:
    client = FakeLlmClient(json.dumps(VALID_PAYLOAD))
    TrendAgent(client).analyze(CANDIDATE)
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "New agent tooling ships" in prompt
    assert "open agent framework" in prompt
    assert prompt == build_trend_prompt(CANDIDATE)


def test_malformed_json_raises_trend_agent_error() -> None:
    client = FakeLlmClient("not json")
    with pytest.raises(TrendAgentError, match="not valid JSON"):
        TrendAgent(client).analyze(CANDIDATE)


def test_prose_around_json_raises_trend_agent_error() -> None:
    wrapped = "Here is the result:\n" + json.dumps(VALID_PAYLOAD)
    client = FakeLlmClient(wrapped)
    with pytest.raises(TrendAgentError, match="not valid JSON"):
        TrendAgent(client).analyze(CANDIDATE)


def test_missing_required_fields_raises_trend_agent_error() -> None:
    client = FakeLlmClient(json.dumps({"summary": "Only a summary"}))
    with pytest.raises(TrendAgentError, match="TrendAnalysis validation"):
        TrendAgent(client).analyze(CANDIDATE)


def test_relevance_score_out_of_range_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "relevance_score": 1.4}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(TrendAgentError, match="TrendAnalysis validation"):
        TrendAgent(client).analyze(CANDIDATE)


def test_blank_summary_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "summary": "   "}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(TrendAgentError, match="TrendAnalysis validation"):
        TrendAgent(client).analyze(CANDIDATE)


def test_blank_category_is_rejected() -> None:
    payload = {**VALID_PAYLOAD, "category": ""}
    client = FakeLlmClient(json.dumps(payload))
    with pytest.raises(TrendAgentError, match="TrendAnalysis validation"):
        TrendAgent(client).analyze(CANDIDATE)
