from typing import Any

import litellm

from app.llm.errors import LlmClientError


def _response_text(response: Any) -> str:
    try:
        choices = response.choices
        content = choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise LlmClientError("LiteLLM returned an unusable response") from exc

    if not isinstance(content, str) or not content.strip():
        raise LlmClientError("LiteLLM returned no usable response content")
    return content


class LiteLlmClient:
    """LlmClient adapter. Isolates LiteLLM from agents and domain code."""

    def __init__(
        self,
        model: str,
        json_schema: dict[str, Any] | None = None,
        json_schema_name: str = "trend_analysis",
    ) -> None:
        stripped = model.strip()
        if not stripped:
            raise LlmClientError("model name is required")
        self._model = stripped
        self._json_schema = json_schema
        self._json_schema_name = json_schema_name.strip() or "trend_analysis"

    def complete(self, prompt: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self._json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": self._json_schema_name,
                    "schema": self._json_schema,
                },
            }
        try:
            response = litellm.completion(**kwargs)
        except LlmClientError:
            raise
        except Exception as exc:
            raise LlmClientError(
                f"LiteLLM completion failed for model {self._model}"
            ) from exc
        return _response_text(response)
