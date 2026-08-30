import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article
from app.pipeline.results import PipelineItem


class StoredArticle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url: str
    canonical_url: str
    title: str
    excerpt: str | None
    published_at: datetime | None
    summary: str
    category: str
    relevance_score: float
    key_points: list[str]
    accepted: bool
    quality_reason: str | None
    created_at: datetime
    updated_at: datetime


def _apply_pipeline_item(article: Article, item: PipelineItem) -> None:
    candidate = item.candidate
    analysis = item.analysis
    decision = item.decision
    assert analysis is not None
    assert decision is not None
    article.source_url = str(candidate.source_url)
    article.canonical_url = str(candidate.canonical_url)
    article.title = candidate.title
    article.excerpt = candidate.excerpt
    article.published_at = candidate.published_at
    article.summary = analysis.summary
    article.category = analysis.category
    article.relevance_score = analysis.relevance_score
    article.key_points = list(analysis.key_points)
    article.accepted = decision.accepted
    article.quality_reason = decision.reason
    article.updated_at = datetime.now(UTC)


class ArticleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_pipeline_item(self, item: PipelineItem) -> StoredArticle | None:
        if item.error is not None or item.analysis is None or item.decision is None:
            return None

        canonical_url = str(item.candidate.canonical_url)
        article = self._session.scalar(
            select(Article).where(Article.canonical_url == canonical_url)
        )
        if article is None:
            article = Article()
            _apply_pipeline_item(article, item)
            self._session.add(article)
        else:
            _apply_pipeline_item(article, item)
        self._session.flush()
        return StoredArticle.model_validate(article)

    def get_by_canonical_url(self, url: str) -> StoredArticle | None:
        article = self._session.scalar(
            select(Article).where(Article.canonical_url == url)
        )
        if article is None:
            return None
        return StoredArticle.model_validate(article)
