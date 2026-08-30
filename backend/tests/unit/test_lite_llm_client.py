import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agents import TrendAgent
from app.domain.models import ArticleCandidate
from app.llm.errors import LlmClientError
from app.llm.lite import LiteLlmClient

CANDIDATE = ArticleCandidate(
    source_url="https://example.com/rss.xml",
    canonical_url="https://example.com/articles/agents",
    title="New agent tooling ships",
    excerpt="A lab released an open agent framework for enterprise workflows.",
    published_at=datetime(2026, 8, 30, tzinfo=UTC),
)

VALID_JSON = json.dumps(
    {
        "summary": "A new open agent framework may speed enterprise automation.",
        "category": "Agentic AI",
        "relevance_score": 0.82,
        "key_points": ["Open framework released", "Aimed at enterprise workflows"],
    }
)


def _response(content: object) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_complete_passes_prompt_and_model_to_litellm() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch("app.llm.lite.litellm.completion", return_value=_response("ok")) as mock:
        result = client.complete("classify this article")

    assert result == "ok"
    mock.assert_called_once_with(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "classify this article"}],
    )
    assert "response_format" not in mock.call_args.kwargs


def test_configured_model_name_is_passed_through() -> None:
    client = LiteLlmClient(model="  claude-sonnet-4-5  ")
    with patch("app.llm.lite.litellm.completion", return_value=_response("ok")) as mock:
        client.complete("hello")

    assert mock.call_args.kwargs["model"] == "claude-sonnet-4-5"
    assert "response_format" not in mock.call_args.kwargs


def test_json_schema_is_passed_as_structured_response_format() -> None:
    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
    }
    client = LiteLlmClient(model="claude-haiku-4-5", json_schema=schema)
    with patch("app.llm.lite.litellm.completion", return_value=_response("{}")) as mock:
        result = client.complete("classify this article")

    assert result == "{}"
    mock.assert_called_once_with(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "classify this article"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "trend_analysis",
                "schema": schema,
            },
        },
    )


def test_response_content_is_returned_as_plain_string() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch(
        "app.llm.lite.litellm.completion",
        return_value=_response("  structured later  "),
    ):
        assert client.complete("prompt") == "  structured later  "


def test_litellm_failure_raises_llm_client_error() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch(
        "app.llm.lite.litellm.completion",
        side_effect=RuntimeError("provider timeout"),
    ):
        with pytest.raises(
            LlmClientError, match="LiteLLM completion failed"
        ) as exc_info:
            client.complete("prompt")
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_missing_content_fails_explicitly() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch("app.llm.lite.litellm.completion", return_value=_response(None)):
        with pytest.raises(LlmClientError, match="no usable response content"):
            client.complete("prompt")


def test_empty_content_fails_explicitly() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch("app.llm.lite.litellm.completion", return_value=_response("   ")):
        with pytest.raises(LlmClientError, match="no usable response content"):
            client.complete("prompt")


def test_unusable_response_shape_fails_explicitly() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch("app.llm.lite.litellm.completion", return_value=SimpleNamespace()):
        with pytest.raises(LlmClientError, match="unusable response"):
            client.complete("prompt")


def test_blank_model_name_is_rejected() -> None:
    with pytest.raises(LlmClientError, match="model name is required"):
        LiteLlmClient(model="   ")


def test_trend_agent_accepts_lite_llm_client_via_protocol() -> None:
    client = LiteLlmClient(model="gpt-4o-mini")
    with patch("app.llm.lite.litellm.completion", return_value=_response(VALID_JSON)):
        analysis = TrendAgent(client).analyze(CANDIDATE)
    assert analysis.category == "Agentic AI"
    assert analysis.relevance_score == 0.82
