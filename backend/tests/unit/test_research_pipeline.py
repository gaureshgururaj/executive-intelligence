import json
from datetime import UTC, datetime

from app.domain.models import PaperCandidate
from app.llm.errors import LlmClientError
from app.pipeline import ResearchPipeline
from app.quality import ResearchQualityGate

NOW = datetime(2026, 9, 1, tzinfo=UTC)

ACCEPTED = PaperCandidate(
    arxiv_id="2401.00001",
    title="Accepted paper",
    abstract="A routing method that reduces failed tool calls.",
    authors=["Ada Lovelace"],
    published_at=NOW,
    updated_at=NOW,
    paper_url="http://arxiv.org/abs/2401.00001v1",
    categories=["cs.LG"],
)

REJECTED = PaperCandidate(
    arxiv_id="2401.00002",
    title="Rejected paper",
    abstract="A minor theoretical note with little executive relevance.",
    authors=["Alan Turing"],
    published_at=NOW,
    updated_at=NOW,
    paper_url="http://arxiv.org/abs/2401.00002v1",
    categories=["cs.AI"],
)

FAILED = PaperCandidate(
    arxiv_id="2401.00003",
    title="Failed paper",
    abstract="This analysis will not parse.",
    authors=["Grace Hopper"],
    published_at=NOW,
    updated_at=NOW,
    paper_url="http://arxiv.org/abs/2401.00003v1",
    categories=["cs.CL"],
)

ACCEPTED_JSON = json.dumps(
    {
        "summary": "A routing method may cut failed tool calls.",
        "category": "Agentic AI",
        "relevance_score": 0.9,
        "key_findings": ["Routing reduced failed tool calls"],
        "practical_implications": ["Watch routing as a reliability lever"],
    }
)

REJECTED_JSON = json.dumps(
    {
        "summary": "Minor theoretical note with little strategic impact.",
        "category": "Other",
        "relevance_score": 0.2,
        "key_findings": ["Minor theoretical note"],
        "practical_implications": [],
    }
)


class MappingLlmClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.complete_calls = 0

    def complete(self, prompt: str) -> str:
        self.complete_calls += 1
        for title, response in self.responses.items():
            if title in prompt:
                return response
        raise AssertionError(f"no LLM fixture for prompt: {prompt}")


def _pipeline(llm: MappingLlmClient | None = None) -> ResearchPipeline:
    client = llm or MappingLlmClient(
        {
            ACCEPTED.title: ACCEPTED_JSON,
            REJECTED.title: REJECTED_JSON,
            FAILED.title: "not json",
        }
    )
    return ResearchPipeline(llm=client, quality_gate=ResearchQualityGate())


def test_accepted_paper_has_analysis_and_decision() -> None:
    item = _pipeline().process_candidates([ACCEPTED])[0]
    assert item.candidate == ACCEPTED
    assert item.analysis is not None
    assert item.analysis.category == "Agentic AI"
    assert item.decision is not None
    assert item.decision.accepted is True
    assert item.error is None


def test_low_relevance_paper_is_rejected() -> None:
    item = _pipeline().process_candidates([REJECTED])[0]
    assert item.candidate == REJECTED
    assert item.analysis is not None
    assert item.analysis.relevance_score == 0.2
    assert item.decision is not None
    assert item.decision.accepted is False
    assert item.decision.reason == "Relevance score below threshold"
    assert item.error is None


def test_research_agent_failure_does_not_erase_neighbors() -> None:
    items = _pipeline().process_candidates([ACCEPTED, FAILED, REJECTED])
    assert items[0].decision is not None and items[0].decision.accepted is True
    assert items[1].error == "LLM output is not valid JSON"
    assert items[1].analysis is None
    assert items[1].decision is None
    assert items[2].decision is not None and items[2].decision.accepted is False


def test_llm_client_error_does_not_erase_neighbors() -> None:
    class MixedLlmClient:
        def complete(self, prompt: str) -> str:
            if FAILED.title in prompt:
                raise LlmClientError("LiteLLM completion failed for model test")
            if ACCEPTED.title in prompt:
                return ACCEPTED_JSON
            if REJECTED.title in prompt:
                return REJECTED_JSON
            raise AssertionError(f"no LLM fixture for prompt: {prompt}")

    items = ResearchPipeline(
        llm=MixedLlmClient(),
        quality_gate=ResearchQualityGate(),
    ).process_candidates([ACCEPTED, FAILED, REJECTED])

    assert items[0].decision is not None and items[0].decision.accepted is True
    assert items[1].error == "LiteLLM completion failed for model test"
    assert items[1].analysis is None
    assert items[1].decision is None
    assert items[2].decision is not None and items[2].decision.accepted is False


def test_output_order_matches_input_order() -> None:
    items = _pipeline().process_candidates([REJECTED, ACCEPTED, FAILED])
    assert [item.candidate.arxiv_id for item in items] == [
        REJECTED.arxiv_id,
        ACCEPTED.arxiv_id,
        FAILED.arxiv_id,
    ]


def test_pipeline_uses_supplied_llm_client() -> None:
    llm = MappingLlmClient({ACCEPTED.title: ACCEPTED_JSON})
    _pipeline(llm).process_candidates([ACCEPTED])
    assert llm.complete_calls == 1
