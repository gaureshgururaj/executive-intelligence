import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.models import PaperCandidate
from app.ingestion.errors import ArxivFetchError
from app.llm.errors import LlmClientError
from app.pipeline import ResearchIngestion, ResearchIngestionItemResult
from app.quality import ResearchQualityGate
from app.repositories.papers import StoredPaper

QUERY = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL"
NOW = datetime(2026, 9, 1, tzinfo=UTC)
LATER = datetime(2026, 9, 3, tzinfo=UTC)

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

CHANGED = PaperCandidate(
    arxiv_id="2401.00004",
    title="Changed paper",
    abstract="Original abstract.",
    authors=["Original Author"],
    published_at=NOW,
    updated_at=NOW,
    paper_url="http://arxiv.org/abs/2401.00004v1",
    categories=["cs.LG"],
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

CHANGED_JSON = json.dumps(
    {
        "summary": "The paper was updated and needs a fresh briefing.",
        "category": "LLMs",
        "relevance_score": 0.7,
        "key_findings": ["Updated method"],
        "practical_implications": ["Revisit prior assumptions"],
    }
)


class MappingLlmClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.complete_calls = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.complete_calls += 1
        self.prompts.append(prompt)
        for title, response in self.responses.items():
            if title in prompt:
                return response
        raise AssertionError(f"no LLM fixture for prompt: {prompt}")


def _mapping_llm() -> MappingLlmClient:
    return MappingLlmClient(
        {
            ACCEPTED.title: ACCEPTED_JSON,
            REJECTED.title: REJECTED_JSON,
            FAILED.title: "not json",
            CHANGED.title: CHANGED_JSON,
        }
    )


def _stored(candidate: PaperCandidate, *, accepted: bool) -> StoredPaper:
    return StoredPaper(
        id=uuid4(),
        arxiv_id=candidate.arxiv_id,
        title=candidate.title,
        abstract=candidate.abstract,
        authors=list(candidate.authors),
        published_at=candidate.published_at,
        arxiv_updated_at=candidate.updated_at,
        paper_url=str(candidate.paper_url),
        pdf_url=str(candidate.pdf_url) if candidate.pdf_url else None,
        categories=list(candidate.categories),
        summary="Existing summary",
        category="Existing",
        relevance_score=0.9 if accepted else 0.2,
        key_findings=["Existing finding"],
        practical_implications=[],
        accepted=accepted,
        quality_reason=None if accepted else "Relevance score below threshold",
        created_at=NOW,
        updated_at=NOW,
    )


def _run(
    candidates: list[PaperCandidate],
    llm: MappingLlmClient | None = None,
    *,
    max_results: int = 10,
    known: dict[str, StoredPaper] | None = None,
) -> tuple[list[ResearchIngestionItemResult], MagicMock, MagicMock, MappingLlmClient]:
    client = llm or _mapping_llm()
    session = MagicMock()
    repository = MagicMock()
    repository.get_by_arxiv_ids.return_value = known or {}
    with (
        patch(
            "app.pipeline.research_ingestion.ingest_arxiv",
            return_value=candidates,
        ) as ingest,
        patch(
            "app.pipeline.research_ingestion.PaperRepository",
            return_value=repository,
        ),
    ):
        results = ResearchIngestion(client, quality_gate=ResearchQualityGate()).run(
            QUERY,
            session,
            max_results=max_results,
        )
    ingest.assert_called_once()
    assert ingest.call_args.kwargs["max_results"] == max_results
    return results, session, repository, client


def test_new_paper_calls_llm_once_and_saves() -> None:
    results, _, repository, llm = _run([ACCEPTED], known={})
    assert llm.complete_calls == 1
    assert repository.save.call_count == 1
    assert results[0].skipped is False
    assert results[0].item is not None
    assert results[0].item.error is None
    saved = repository.save.call_args.args
    assert saved[0].arxiv_id == ACCEPTED.arxiv_id
    assert saved[2].accepted is True


def test_unchanged_paper_is_skipped_without_llm_or_save() -> None:
    stored = _stored(ACCEPTED, accepted=True)
    results, _, repository, llm = _run(
        [ACCEPTED],
        known={ACCEPTED.arxiv_id: stored},
    )
    assert llm.complete_calls == 0
    repository.save.assert_not_called()
    assert results == [
        ResearchIngestionItemResult(item=None, stored=stored, skipped=True),
    ]


def test_unchanged_rejected_row_is_skipped() -> None:
    stored = _stored(REJECTED, accepted=False)
    results, _, repository, llm = _run(
        [REJECTED],
        known={REJECTED.arxiv_id: stored},
    )
    assert llm.complete_calls == 0
    repository.save.assert_not_called()
    assert results[0].skipped is True
    assert results[0].item is None
    assert results[0].stored is stored
    assert results[0].stored is not None
    assert results[0].stored.accepted is False


def test_changed_title_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(update={"title": "New title"})
    llm = MappingLlmClient({"New title": CHANGED_JSON})
    _, _, repository, client = _run(
        [candidate],
        llm=llm,
        known={CHANGED.arxiv_id: stored},
    )
    assert client.complete_calls == 1
    assert repository.save.call_count == 1


def test_changed_abstract_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(update={"abstract": "New abstract."})
    _, _, repository, llm = _run(
        [candidate],
        known={CHANGED.arxiv_id: stored},
    )
    assert llm.complete_calls == 1
    assert repository.save.call_count == 1


def test_changed_updated_at_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(update={"updated_at": LATER})
    _, _, repository, llm = _run(
        [candidate],
        known={CHANGED.arxiv_id: stored},
    )
    assert llm.complete_calls == 1
    assert repository.save.call_count == 1


def test_same_unversioned_id_with_new_version_content_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(
        update={
            "abstract": "v2 abstract with a new method.",
            "updated_at": LATER,
            "paper_url": "http://arxiv.org/abs/2401.00004v2",
        }
    )
    results, _, repository, llm = _run(
        [candidate],
        known={CHANGED.arxiv_id: stored},
    )
    assert candidate.arxiv_id == stored.arxiv_id
    assert llm.complete_calls == 1
    assert repository.save.call_count == 1
    assert results[0].skipped is False


def test_rejected_analysis_is_saved() -> None:
    _, _, repository, _ = _run([REJECTED], known={})
    assert repository.save.call_count == 1
    decision = repository.save.call_args.args[2]
    assert decision.accepted is False


def test_agent_failure_is_not_persisted() -> None:
    results, _, repository, llm = _run([ACCEPTED, FAILED])
    saved_ids = [call.args[0].arxiv_id for call in repository.save.call_args_list]
    assert llm.complete_calls == 2
    assert saved_ids == [ACCEPTED.arxiv_id]
    assert results[1].skipped is False
    assert results[1].stored is None
    assert results[1].item is not None
    assert results[1].item.error is not None


def test_llm_client_error_is_not_persisted() -> None:
    class MixedLlmClient:
        def __init__(self) -> None:
            self.complete_calls = 0

        def complete(self, prompt: str) -> str:
            self.complete_calls += 1
            if FAILED.title in prompt:
                raise LlmClientError("LiteLLM completion failed for model test")
            if ACCEPTED.title in prompt:
                return ACCEPTED_JSON
            raise AssertionError(f"no LLM fixture for prompt: {prompt}")

    llm = MixedLlmClient()
    results, _, repository, _ = _run([ACCEPTED, FAILED], llm=llm)
    saved_ids = [call.args[0].arxiv_id for call in repository.save.call_args_list]
    assert llm.complete_calls == 2
    assert saved_ids == [ACCEPTED.arxiv_id]
    assert results[1].item is not None
    assert results[1].item.error == "LiteLLM completion failed for model test"


def test_mixed_batch_preserves_arxiv_order_and_one_lookup() -> None:
    accepted_stored = _stored(ACCEPTED, accepted=True)
    changed_stored = _stored(CHANGED, accepted=True)
    changed = CHANGED.model_copy(update={"title": "Updated changed title"})
    llm = MappingLlmClient(
        {
            REJECTED.title: REJECTED_JSON,
            "Updated changed title": CHANGED_JSON,
            FAILED.title: "not json",
        }
    )
    results, _, repository, client = _run(
        [ACCEPTED, REJECTED, changed, FAILED],
        llm=llm,
        known={
            ACCEPTED.arxiv_id: accepted_stored,
            CHANGED.arxiv_id: changed_stored,
        },
    )
    assert client.complete_calls == 3
    assert ACCEPTED.title not in "".join(client.prompts)
    assert results[0].skipped is True
    assert results[1].skipped is False
    assert results[2].skipped is False
    assert results[3].skipped is False
    assert results[3].item is not None
    assert results[3].item.error is not None
    assert [
        ACCEPTED.arxiv_id,
        results[1].item.candidate.arxiv_id if results[1].item else None,
        results[2].item.candidate.arxiv_id if results[2].item else None,
        results[3].item.candidate.arxiv_id if results[3].item else None,
    ] == [
        ACCEPTED.arxiv_id,
        REJECTED.arxiv_id,
        CHANGED.arxiv_id,
        FAILED.arxiv_id,
    ]
    repository.get_by_arxiv_ids.assert_called_once_with(
        [
            ACCEPTED.arxiv_id,
            REJECTED.arxiv_id,
            CHANGED.arxiv_id,
            FAILED.arxiv_id,
        ]
    )
    repository.get_by_arxiv_id.assert_not_called()


def test_max_results_is_passed_to_ingest_arxiv_only_once() -> None:
    results, _, repository, llm = _run(
        [ACCEPTED, REJECTED, FAILED, CHANGED],
        max_results=4,
    )
    assert llm.complete_calls == 4
    assert len(results) == 4
    repository.get_by_arxiv_ids.assert_called_once()


def test_session_is_not_committed_rolled_back_or_closed() -> None:
    _, session, _, _ = _run([ACCEPTED])
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()


def test_arxiv_fetch_error_propagates_without_saving() -> None:
    session = MagicMock()
    repository = MagicMock()
    with (
        patch(
            "app.pipeline.research_ingestion.ingest_arxiv",
            side_effect=ArxivFetchError("Unparseable arXiv feed"),
        ),
        patch(
            "app.pipeline.research_ingestion.PaperRepository",
            return_value=repository,
        ),
        pytest.raises(ArxivFetchError, match="Unparseable arXiv feed"),
    ):
        ResearchIngestion(_mapping_llm()).run(QUERY, session, max_results=5)
    repository.get_by_arxiv_ids.assert_not_called()
    repository.save.assert_not_called()
    session.commit.assert_not_called()


def test_save_exception_propagates() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.get_by_arxiv_ids.return_value = {}
    repository.save.side_effect = RuntimeError("flush failed")
    with (
        patch(
            "app.pipeline.research_ingestion.ingest_arxiv",
            return_value=[ACCEPTED],
        ),
        patch(
            "app.pipeline.research_ingestion.PaperRepository",
            return_value=repository,
        ),
        pytest.raises(RuntimeError, match="flush failed"),
    ):
        ResearchIngestion(_mapping_llm()).run(QUERY, session, max_results=5)
    session.rollback.assert_not_called()
    session.commit.assert_not_called()
