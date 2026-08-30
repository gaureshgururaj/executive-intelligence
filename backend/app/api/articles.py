import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import ArticleRepository, StoredArticle

router = APIRouter(prefix="/api/v1")


class ArticleFeedItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_url: str
    title: str
    excerpt: str | None
    published_at: datetime | None
    summary: str
    category: str
    relevance_score: float
    key_points: list[str]
    created_at: datetime


def _to_feed_item(article: StoredArticle) -> ArticleFeedItem:
    return ArticleFeedItem.model_validate(article)


@router.get("/articles", response_model=list[ArticleFeedItem])
def list_articles(session: Session = Depends(get_db)) -> list[ArticleFeedItem]:
    return [
        _to_feed_item(article) for article in ArticleRepository(session).list_accepted()
    ]
