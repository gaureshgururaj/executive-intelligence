"""Manual live smoke test for LiteLlmClient. Not invoked by pytest.

Requires a provider API key in the environment, for example:
  OPENAI_API_KEY
  ANTHROPIC_API_KEY

Model name comes from LLM_MODEL (see repo-root .env / .env.example).

From backend/:

  PYTHONPATH=. python scripts/smoke_lite_llm.py
"""

from app.config import get_settings
from app.llm.lite import LiteLlmClient


def main() -> None:
    settings = get_settings()
    client = LiteLlmClient(model=settings.llm_model)
    print(client.complete("Reply with the single word: pong"))


if __name__ == "__main__":
    main()
