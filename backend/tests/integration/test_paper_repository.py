from datetime import UTC, datetime
from unittest.mock import MagicMock

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.models import PaperCandidate, QualityDecision, ResearchAnalysis
from app.repositories import PaperRepository

ARXIV_ID = "2401.00001"
PUBLISHED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
ARXIV_UPDATED_AT = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> PaperCandidate:
    payload: dict[str, object] = {
        "arxiv_id": ARXIV_ID,
        "title": "Mixture-of-experts routing improves tool use",
        "abstract": "The authors propose a routing method for multi-agent systems.",
        "authors": ["Ada Lovelace", "Alan Turing"],
        "published_at": PUBLISHED_AT,
        "updated_at": ARXIV_UPDATED_AT,
        "paper_url": "http://arxiv.org/abs/2401.00001v1",
        "pdf_url": "http://arxiv.org/pdf/2401.00001v1",
        "categories": ["cs.LG", "cs.AI"],
    }
    payload.update(overrides)
    return PaperCandidate.model_validate(payload)


def _analysis(**overrides: object) -> ResearchAnalysis:
    payload: dict[str, object] = {
        "summary": "A routing method may cut failed tool calls in multi-agent systems.",
        "category": "Agentic AI",
        "relevance_score": 0.82,
        "key_findings": ["Routing reduced failed tool calls"],
        "practical_implications": ["Leaders can watch routing as a reliability lever"],
    }
    payload.update(overrides)
    return ResearchAnalysis.model_validate(payload)


def _accepted() -> QualityDecision:
    return QualityDecision(accepted=True, reason=None)


def _rejected() -> QualityDecision:
    return QualityDecision(accepted=False, reason="Relevance score below threshold")


def test_papers_table_uses_postgres_types(postgres_engine: Engine) -> None:
    columns = {
        column["name"]: column
        for column in inspect(postgres_engine).get_columns("papers")
    }
    assert "UUID" in str(columns["id"]["type"]).upper()
    assert "JSON" in str(columns["authors"]["type"]).upper()
    assert "JSON" in str(columns["categories"]["type"]).upper()
    assert "JSON" in str(columns["key_findings"]["type"]).upper()
    assert "JSON" in str(columns["practical_implications"]["type"]).upper()
    assert getattr(columns["published_at"]["type"], "timezone", False) is True
    assert getattr(columns["arxiv_updated_at"]["type"], "timezone", False) is True
    assert getattr(columns["updated_at"]["type"], "timezone", False) is True
    unique_constraints = inspect(postgres_engine).get_unique_constraints("papers")
    unique_indexes = [
        tuple(index["column_names"])
        for index in inspect(postgres_engine).get_indexes("papers")
        if index["unique"]
    ]
    unique_names = {tuple(item["column_names"]) for item in unique_constraints}
    unique_names |= set(unique_indexes)
    assert ("arxiv_id",) in unique_names


def test_accepted_paper_persists(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    assert stored.accepted is True
    assert stored.quality_reason is None
    assert stored.arxiv_id == ARXIV_ID


def test_rejected_paper_persists_with_reason(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(relevance_score=0.2), _rejected())
    assert stored.accepted is False
    assert stored.quality_reason == "Relevance score below threshold"


def test_candidate_fields_round_trip(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    assert stored.title == "Mixture-of-experts routing improves tool use"
    assert stored.abstract.startswith("The authors propose")
    assert stored.authors == ["Ada Lovelace", "Alan Turing"]
    assert stored.categories == ["cs.LG", "cs.AI"]
    assert stored.published_at == PUBLISHED_AT
    assert stored.arxiv_updated_at == ARXIV_UPDATED_AT
    assert stored.paper_url == "http://arxiv.org/abs/2401.00001v1"
    assert stored.pdf_url == "http://arxiv.org/pdf/2401.00001v1"


def test_analysis_fields_round_trip(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    assert stored.summary.startswith("A routing method")
    assert stored.category == "Agentic AI"
    assert stored.relevance_score == 0.82
    assert stored.key_findings == ["Routing reduced failed tool calls"]
    assert stored.practical_implications == [
        "Leaders can watch routing as a reliability lever"
    ]


def test_get_by_arxiv_id_returns_stored_paper(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    saved = repo.save(_candidate(), _analysis(), _accepted())
    fetched = repo.get_by_arxiv_id(ARXIV_ID)
    assert fetched == saved


def test_unknown_arxiv_id_returns_none(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    assert repo.get_by_arxiv_id("missing.00000") is None


def test_upsert_preserves_id_and_created_at(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    first = repo.save(_candidate(), _analysis(), _accepted())
    second = repo.save(
        _candidate(
            title="Updated title",
            abstract="Updated abstract",
            authors=["Grace Hopper"],
            categories=["cs.CL"],
            published_at=None,
            updated_at=datetime(2026, 9, 3, tzinfo=UTC),
            paper_url="http://arxiv.org/abs/2401.00001v2",
            pdf_url=None,
        ),
        _analysis(
            summary="Updated summary",
            category="NLP",
            relevance_score=0.4,
            key_findings=[],
            practical_implications=[],
        ),
        _rejected(),
    )
    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at
    assert second.title == "Updated title"
    assert second.abstract == "Updated abstract"
    assert second.authors == ["Grace Hopper"]
    assert second.categories == ["cs.CL"]
    assert second.published_at is None
    assert second.arxiv_updated_at == datetime(2026, 9, 3, tzinfo=UTC)
    assert second.paper_url == "http://arxiv.org/abs/2401.00001v2"
    assert second.pdf_url is None
    assert second.summary == "Updated summary"
    assert second.category == "NLP"
    assert second.relevance_score == 0.4
    assert second.key_findings == []
    assert second.practical_implications == []
    assert second.accepted is False
    assert second.quality_reason == "Relevance score below threshold"


def test_nullable_source_fields_persist(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(
        _candidate(published_at=None, updated_at=None, pdf_url=None),
        _analysis(),
        _accepted(),
    )
    assert stored.published_at is None
    assert stored.arxiv_updated_at is None
    assert stored.pdf_url is None


def test_arxiv_updated_at_is_distinct_from_row_updated_at(
    db_session: Session,
) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    assert stored.arxiv_updated_at == ARXIV_UPDATED_AT
    assert stored.updated_at != stored.arxiv_updated_at


def test_save_flushes_but_does_not_commit(db_session: Session) -> None:
    db_session.commit = MagicMock()
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    db_session.commit.assert_not_called()
    assert repo.get_by_arxiv_id(stored.arxiv_id) == stored


def test_get_by_arxiv_ids_returns_empty_for_no_ids(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    assert repo.get_by_arxiv_ids([]) == {}


def test_get_by_arxiv_ids_returns_known_rows_only(db_session: Session) -> None:
    repo = PaperRepository(db_session)
    saved = repo.save(_candidate(), _analysis(), _accepted())
    found = repo.get_by_arxiv_ids([ARXIV_ID, "missing.00000"])
    assert list(found) == [ARXIV_ID]
    assert found[ARXIV_ID] == saved
