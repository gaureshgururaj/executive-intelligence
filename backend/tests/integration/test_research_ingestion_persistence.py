import json
from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.models import PaperCandidate
from app.pipeline import ResearchIngestion
from app.quality import ResearchQualityGate
from app.repositories import PaperRepository

QUERY = "cat:cs.AI"
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

UPDATED_JSON = json.dumps(
    {
        "summary": "Updated summary after a second ingest.",
        "category": "LLMs",
        "relevance_score": 0.4,
        "key_findings": ["Only one finding"],
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


def _llm() -> MappingLlmClient:
    return MappingLlmClient(
        {
            ACCEPTED.title: ACCEPTED_JSON,
            REJECTED.title: REJECTED_JSON,
            FAILED.title: "not json",
        }
    )


def test_accepted_and_rejected_persist_failed_does_not(db_session: Session) -> None:
    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[ACCEPTED, REJECTED, FAILED],
    ):
        results = ResearchIngestion(_llm(), quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=3,
        )

    repo = PaperRepository(db_session)
    accepted = repo.get_by_arxiv_id(ACCEPTED.arxiv_id)
    rejected = repo.get_by_arxiv_id(REJECTED.arxiv_id)
    assert accepted is not None
    assert accepted.accepted is True
    assert rejected is not None
    assert rejected.accepted is False
    assert rejected.quality_reason == "Relevance score below threshold"
    assert repo.get_by_arxiv_id(FAILED.arxiv_id) is None
    assert results[2].stored is None
    assert results[2].skipped is False
    assert results[2].item is not None
    assert results[2].item.error is not None


def test_research_ingestion_does_not_commit(
    db_session: Session, postgres_engine: Engine
) -> None:
    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[ACCEPTED],
    ):
        ResearchIngestion(_llm(), quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )

    assert PaperRepository(db_session).get_by_arxiv_id(ACCEPTED.arxiv_id) is not None

    with Session(postgres_engine) as other:
        assert PaperRepository(other).get_by_arxiv_id(ACCEPTED.arxiv_id) is None


def test_unchanged_accepted_paper_is_skipped(db_session: Session) -> None:
    llm = MappingLlmClient({ACCEPTED.title: ACCEPTED_JSON})
    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[ACCEPTED],
    ):
        first = ResearchIngestion(llm, quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )
    assert first[0].stored is not None
    first_updated = first[0].stored.updated_at
    calls_after_insert = llm.complete_calls

    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[ACCEPTED],
    ):
        second = ResearchIngestion(llm, quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )

    assert llm.complete_calls == calls_after_insert
    assert second[0].skipped is True
    assert second[0].item is None
    assert second[0].stored is not None
    assert second[0].stored.id == first[0].stored.id
    assert second[0].stored.updated_at == first_updated
    assert second[0].stored.summary == first[0].stored.summary


def test_unchanged_rejected_paper_is_skipped(db_session: Session) -> None:
    llm = MappingLlmClient({REJECTED.title: REJECTED_JSON})
    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[REJECTED],
    ):
        first = ResearchIngestion(llm, quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )
    assert first[0].stored is not None
    calls_after_insert = llm.complete_calls

    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[REJECTED],
    ):
        second = ResearchIngestion(llm, quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )

    assert llm.complete_calls == calls_after_insert
    assert second[0].skipped is True
    assert second[0].stored is not None
    assert second[0].stored.accepted is False
    assert second[0].stored.updated_at == first[0].stored.updated_at


def test_changed_title_reprocesses_same_id(db_session: Session) -> None:
    first_llm = MappingLlmClient({ACCEPTED.title: ACCEPTED_JSON})
    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[ACCEPTED],
    ):
        first = ResearchIngestion(first_llm, quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )
    assert first[0].stored is not None

    updated_candidate = ACCEPTED.model_copy(update={"title": "Updated title only"})
    second_llm = MappingLlmClient({"Updated title only": UPDATED_JSON})
    with patch(
        "app.pipeline.research_ingestion.ingest_arxiv",
        return_value=[updated_candidate],
    ):
        second = ResearchIngestion(second_llm, quality_gate=ResearchQualityGate()).run(
            QUERY,
            db_session,
            max_results=1,
        )
    stored = second[0].stored
    assert second[0].skipped is False
    assert stored is not None
    assert stored.id == first[0].stored.id
    assert stored.title == "Updated title only"
    assert stored.summary == "Updated summary after a second ingest."
    assert stored.updated_at >= first[0].stored.updated_at
    assert stored.created_at == first[0].stored.created_at
