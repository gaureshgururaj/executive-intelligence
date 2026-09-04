import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import PaperRepository, StoredPaper

router = APIRouter(prefix="/api/v1")


class PaperFeedItem(BaseModel):
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
    created_at: datetime


def _to_feed_item(paper: StoredPaper) -> PaperFeedItem:
    return PaperFeedItem.model_validate(paper)


@router.get("/papers", response_model=list[PaperFeedItem])
def list_papers(session: Session = Depends(get_db)) -> list[PaperFeedItem]:
    return [_to_feed_item(paper) for paper in PaperRepository(session).list_accepted()]
