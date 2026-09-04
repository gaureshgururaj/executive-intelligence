import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.articles import ArticleFeedItem
from app.api.papers import PaperFeedItem
from app.db.session import get_db
from app.recommendations.errors import RecommendationProfileNotFoundError
from app.recommendations.service import RankedArticle, RecommendationService
from app.repositories import RecommendationProfileRepository

router = APIRouter(prefix="/api/v1")


class RecommendationProfileItem(BaseModel):
    id: uuid.UUID
    name: str
    interests: list[str]


class ArticleRecommendationItem(BaseModel):
    content_type: Literal["article"] = "article"
    recommendation_score: float
    matched_interests: list[str]
    reason: str
    item: ArticleFeedItem


class PaperRecommendationItem(BaseModel):
    content_type: Literal["paper"] = "paper"
    recommendation_score: float
    matched_interests: list[str]
    reason: str
    item: PaperFeedItem


RecommendationFeedItem = Annotated[
    ArticleRecommendationItem | PaperRecommendationItem,
    Field(discriminator="content_type"),
]


@router.get(
    "/recommendation-profiles",
    response_model=list[RecommendationProfileItem],
)
def list_recommendation_profiles(
    session: Session = Depends(get_db),
) -> list[RecommendationProfileItem]:
    return [
        RecommendationProfileItem(
            id=profile.id,
            name=profile.name,
            interests=list(profile.interests),
        )
        for profile in RecommendationProfileRepository(session).list_all()
    ]


@router.get("/recommendations", response_model=list[RecommendationFeedItem])
def list_recommendations(
    profile_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> list[ArticleRecommendationItem | PaperRecommendationItem]:
    try:
        feed = RecommendationService(session).recommend_feed_for_profile(profile_id)
    except RecommendationProfileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Recommendation profile not found",
        ) from None
    items: list[ArticleRecommendationItem | PaperRecommendationItem] = []
    for entry in feed:
        recommendation = entry.recommendation
        if isinstance(entry, RankedArticle):
            items.append(
                ArticleRecommendationItem(
                    recommendation_score=recommendation.recommendation_score,
                    matched_interests=list(recommendation.matched_interests),
                    reason=recommendation.reason,
                    item=ArticleFeedItem.model_validate(entry.article),
                )
            )
        else:
            items.append(
                PaperRecommendationItem(
                    recommendation_score=recommendation.recommendation_score,
                    matched_interests=list(recommendation.matched_interests),
                    reason=recommendation.reason,
                    item=PaperFeedItem.model_validate(entry.paper),
                )
            )
    return items
