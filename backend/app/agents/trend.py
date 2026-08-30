import json

from pydantic import ValidationError

from app.agents.errors import TrendAgentError
from app.domain.models import ArticleCandidate, TrendAnalysis
from app.llm.client import LlmClient

_PROMPT_INSTRUCTIONS = """You are classifying an AI news article for technology
executives.

Return ONLY a JSON object with these keys:
- summary: string, 1-4 sentences, executive tone
- category: string, a concise AI-topic category label
- relevance_score: number between 0 and 1
- key_points: array of 2-5 short strings

Do not include markdown or any text outside the JSON object."""


def build_trend_prompt(candidate: ArticleCandidate) -> str:
    excerpt = candidate.excerpt if candidate.excerpt is not None else "(none)"
    return (
        f"{_PROMPT_INSTRUCTIONS}\n"
        f"\n"
        f"Title: {candidate.title}\n"
        f"Excerpt: {excerpt}\n"
        f"Canonical URL: {candidate.canonical_url}\n"
        f"Source feed: {candidate.source_url}\n"
    )


class TrendAgent:
    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def analyze(self, candidate: ArticleCandidate) -> TrendAnalysis:
        raw = self._llm.complete(build_trend_prompt(candidate))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TrendAgentError("LLM output is not valid JSON") from exc
        try:
            return TrendAnalysis.model_validate(payload)
        except ValidationError as exc:
            raise TrendAgentError("LLM output failed TrendAnalysis validation") from exc
