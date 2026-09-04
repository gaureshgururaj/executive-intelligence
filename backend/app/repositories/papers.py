import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Paper
from app.domain.models import PaperCandidate, QualityDecision, ResearchAnalysis


class StoredPaper(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published_at: datetime | None
    arxiv_updated_at: datetime | None
    paper_url: str
    pdf_url: str | None
    categories: list[str]
    summary: str
    category: str
    relevance_score: float
    key_findings: list[str]
    practical_implications: list[str]
    accepted: bool
    quality_reason: str | None
    created_at: datetime
    updated_at: datetime


def _apply(
    paper: Paper,
    candidate: PaperCandidate,
    analysis: ResearchAnalysis,
    decision: QualityDecision,
) -> None:
    paper.arxiv_id = candidate.arxiv_id
    paper.title = candidate.title
    paper.abstract = candidate.abstract
    paper.authors = list(candidate.authors)
    paper.published_at = candidate.published_at
    paper.arxiv_updated_at = candidate.updated_at
    paper.paper_url = str(candidate.paper_url)
    paper.pdf_url = str(candidate.pdf_url) if candidate.pdf_url is not None else None
    paper.categories = list(candidate.categories)
    paper.summary = analysis.summary
    paper.category = analysis.category
    paper.relevance_score = analysis.relevance_score
    paper.key_findings = list(analysis.key_findings)
    paper.practical_implications = list(analysis.practical_implications)
    paper.accepted = decision.accepted
    paper.quality_reason = decision.reason
    paper.updated_at = datetime.now(UTC)


class PaperRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        candidate: PaperCandidate,
        analysis: ResearchAnalysis,
        decision: QualityDecision,
    ) -> StoredPaper:
        paper = self._session.scalar(
            select(Paper).where(Paper.arxiv_id == candidate.arxiv_id)
        )
        if paper is None:
            paper = Paper()
            _apply(paper, candidate, analysis, decision)
            self._session.add(paper)
        else:
            _apply(paper, candidate, analysis, decision)
        self._session.flush()
        return StoredPaper.model_validate(paper)

    def get_by_arxiv_id(self, arxiv_id: str) -> StoredPaper | None:
        paper = self._session.scalar(select(Paper).where(Paper.arxiv_id == arxiv_id))
        if paper is None:
            return None
        return StoredPaper.model_validate(paper)

    def get_by_arxiv_ids(self, arxiv_ids: list[str]) -> dict[str, StoredPaper]:
        if not arxiv_ids:
            return {}
        rows = self._session.scalars(select(Paper).where(Paper.arxiv_id.in_(arxiv_ids)))
        return {row.arxiv_id: StoredPaper.model_validate(row) for row in rows}

    def list_accepted(self) -> list[StoredPaper]:
        rows = self._session.scalars(
            select(Paper)
            .where(Paper.accepted.is_(True))
            .order_by(
                Paper.published_at.desc().nulls_last(),
                Paper.created_at.desc(),
                Paper.id.desc(),
            )
        )
        return [StoredPaper.model_validate(row) for row in rows]
