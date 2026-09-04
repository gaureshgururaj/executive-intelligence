import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.models import Recommendation, RecommendationProfile
from app.recommendations.errors import RecommendationProfileNotFoundError
from app.recommendations.project import recommendable_article, recommendable_paper
from app.recommendations.scoring import recommend
from app.repositories import (
    ArticleRepository,
    PaperRepository,
    RecommendationProfileRepository,
)
from app.repositories.recommendation_profiles import StoredRecommendationProfile


def domain_profile(stored: StoredRecommendationProfile) -> RecommendationProfile:
    return RecommendationProfile(
        id=stored.id,
        name=stored.name,
        interests=list(stored.interests),
    )


class RecommendationService:
    """Load a profile and accepted content, then rank with recommend()."""

    def __init__(self, session: Session) -> None:
        self._profiles = RecommendationProfileRepository(session)
        self._articles = ArticleRepository(session)
        self._papers = PaperRepository(session)

    def recommend_for_profile(
        self,
        profile_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> list[Recommendation]:
        stored = self._profiles.get_by_id(profile_id)
        if stored is None:
            raise RecommendationProfileNotFoundError(profile_id)
        contents = [
            recommendable_article(article) for article in self._articles.list_accepted()
        ]
        contents.extend(
            recommendable_paper(paper) for paper in self._papers.list_accepted()
        )
        return recommend(
            domain_profile(stored),
            contents,
            now=now if now is not None else datetime.now(UTC),
        )
