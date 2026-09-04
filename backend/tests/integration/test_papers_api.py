from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.models import PaperCandidate, QualityDecision, ResearchAnalysis
from app.main import app
from app.repositories import PaperRepository

RESPONSE_FIELDS = {
    "id",
    "arxiv_id",
    "title",
    "abstract",
    "authors",
    "published_at",
    "arxiv_updated_at",
    "paper_url",
    "pdf_url",
    "categories",
    "summary",
    "category",
    "relevance_score",
    "key_findings",
    "practical_implications",
    "created_at",
}


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _candidate(**overrides: object) -> PaperCandidate:
    payload: dict[str, object] = {
        "arxiv_id": "2401.00001",
        "title": "Accepted paper",
        "abstract": "The authors propose a routing method for multi-agent systems.",
        "authors": ["Ada Lovelace", "Alan Turing"],
        "published_at": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 2, 9, 0, tzinfo=UTC),
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


def test_papers_endpoint_returns_empty_list(
    db_session: Session, api_client: TestClient
) -> None:
    response = api_client.get("/api/v1/papers")
    assert response.status_code == 200
    assert response.json() == []


def test_accepted_paper_appears_in_feed(
    db_session: Session, api_client: TestClient
) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    response = api_client.get("/api/v1/papers")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    item = payload[0]
    assert set(item.keys()) == RESPONSE_FIELDS
    assert item["arxiv_id"] == "2401.00001"
    assert item["title"] == "Accepted paper"
    assert item["abstract"] == (
        "The authors propose a routing method for multi-agent systems."
    )
    assert item["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert item["categories"] == ["cs.LG", "cs.AI"]
    assert item["summary"].startswith("A routing method")
    assert item["category"] == "Agentic AI"
    assert item["relevance_score"] == 0.82
    assert item["key_findings"] == ["Routing reduced failed tool calls"]
    assert item["practical_implications"] == [
        "Leaders can watch routing as a reliability lever"
    ]
    assert item["paper_url"] == "http://arxiv.org/abs/2401.00001v1"
    assert item["pdf_url"] == "http://arxiv.org/pdf/2401.00001v1"
    assert UUID(item["id"]) == stored.id
    assert item["published_at"].startswith("2026-09-01")
    assert item["arxiv_updated_at"].startswith("2026-09-02")
    assert item["created_at"]
    assert "accepted" not in item
    assert "quality_reason" not in item
    assert "updated_at" not in item


def test_rejected_paper_does_not_appear(
    db_session: Session, api_client: TestClient
) -> None:
    repo = PaperRepository(db_session)
    repo.save(_candidate(), _analysis(), _accepted())
    repo.save(
        _candidate(arxiv_id="2401.00002", title="Rejected paper"),
        _analysis(relevance_score=0.2),
        _rejected(),
    )
    response = api_client.get("/api/v1/papers")
    titles = [item["title"] for item in response.json()]
    assert titles == ["Accepted paper"]
    rejected = repo.get_by_arxiv_id("2401.00002")
    assert rejected is not None


def test_nullable_source_fields_serialize_as_null(
    db_session: Session, api_client: TestClient
) -> None:
    PaperRepository(db_session).save(
        _candidate(published_at=None, updated_at=None, pdf_url=None),
        _analysis(),
        _accepted(),
    )
    response = api_client.get("/api/v1/papers")
    assert response.status_code == 200
    item = response.json()[0]
    assert item["published_at"] is None
    assert item["arxiv_updated_at"] is None
    assert item["pdf_url"] is None


def test_accepted_papers_are_ordered_by_published_at(
    db_session: Session, api_client: TestClient
) -> None:
    repo = PaperRepository(db_session)
    older = datetime(2026, 8, 1, tzinfo=UTC)
    repo.save(
        _candidate(arxiv_id="2401.00001", title="Older", published_at=older),
        _analysis(),
        _accepted(),
    )
    repo.save(
        _candidate(arxiv_id="2401.00002", title="Undated", published_at=None),
        _analysis(),
        _accepted(),
    )
    repo.save(
        _candidate(
            arxiv_id="2401.00003",
            title="Newer",
            published_at=older + timedelta(days=29),
        ),
        _analysis(),
        _accepted(),
    )
    response = api_client.get("/api/v1/papers")
    assert [item["title"] for item in response.json()] == ["Newer", "Older", "Undated"]


def test_list_papers_is_read_only(db_session: Session, api_client: TestClient) -> None:
    repo = PaperRepository(db_session)
    stored = repo.save(_candidate(), _analysis(), _accepted())
    updated_before = stored.updated_at
    api_client.get("/api/v1/papers")
    fetched = repo.get_by_arxiv_id(stored.arxiv_id)
    assert fetched is not None
    assert fetched.updated_at == updated_before
    assert fetched.title == stored.title
