import json
from datetime import datetime

from pydantic import ValidationError

from app.agents.errors import ResearchAgentError
from app.domain.models import PaperCandidate, ResearchAnalysis
from app.llm.client import LlmClient

_PROMPT_INSTRUCTIONS = """You are analyzing an AI research paper for technology
executives and technical leaders.

Use only the paper fields provided below. Do not invent citation counts,
download counts, social influence, production readiness, unsupported business
impact, or any fact that is not present in those fields.

Explain:
- what the paper did
- what matters
- why a technology leader may care, only when the abstract supports it

Return useful key_findings and practical_implications when the paper supports
them. If the abstract does not support findings or implications, use an empty
array. Do not invent implications just to fill a count.

Return ONLY a JSON object with these keys:
- summary: string, 1-4 sentences, executive tone
- category: string, a concise AI-topic category label
- relevance_score: number between 0 and 1
- key_findings: array of short strings
- practical_implications: array of short strings

Do not include markdown or any text outside the JSON object."""


def _optional_datetime(value: datetime | None) -> str:
    if value is None:
        return "(none)"
    return value.isoformat()


def build_research_prompt(candidate: PaperCandidate) -> str:
    authors = ", ".join(candidate.authors)
    categories = ", ".join(candidate.categories) or "(none)"
    return (
        f"{_PROMPT_INSTRUCTIONS}\n"
        f"\n"
        f"Title: {candidate.title}\n"
        f"Abstract: {candidate.abstract}\n"
        f"Authors: {authors}\n"
        f"Categories: {categories}\n"
        f"Published: {_optional_datetime(candidate.published_at)}\n"
        f"Updated: {_optional_datetime(candidate.updated_at)}\n"
    )


class ResearchAgent:
    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def analyze(self, candidate: PaperCandidate) -> ResearchAnalysis:
        raw = self._llm.complete(build_research_prompt(candidate))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ResearchAgentError("LLM output is not valid JSON") from exc
        try:
            return ResearchAnalysis.model_validate(payload)
        except ValidationError as exc:
            raise ResearchAgentError(
                "LLM output failed ResearchAnalysis validation"
            ) from exc
