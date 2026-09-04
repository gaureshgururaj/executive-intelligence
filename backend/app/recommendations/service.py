import uuid
from dataclasses import dataclass
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
from app.repositories.articles import StoredArticle
from app.repositories.papers import StoredPaper
from app.repositories.recommendation_profiles import StoredRecommendationProfile


def domain_profile(stored: StoredRecommendationProfile) -> RecommendationProfile:
    return RecommendationProfile(
        id=stored.id,
        name=stored.name,
        interests=list(stored.interests),
    )


@dataclass(frozen=True)
class RankedArticle:
    recommendation: Recommendation
    article: StoredArticle


@dataclass(frozen=True)
class RankedPaper:
    recommendation: Recommendation
    paper: StoredPaper


RankedRecommendation = RankedArticle | RankedPaper


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
        ranked, _, _ = self._rank_for_profile(profile_id, now=now)
        return ranked

    def recommend_feed_for_profile(
        self,
        profile_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> list[RankedRecommendation]:
        ranked, articles, papers = self._rank_for_profile(profile_id, now=now)
        feed: list[RankedRecommendation] = []
        for recommendation in ranked:
            if recommendation.content_type == "article":
                feed.append(
                    RankedArticle(
                        recommendation=recommendation,
                        article=articles[recommendation.content_id],
                    )
                )
            else:
                feed.append(
                    RankedPaper(
                        recommendation=recommendation,
                        paper=papers[recommendation.content_id],
                    )
                )
        return feed

    def _rank_for_profile(
        self,
        profile_id: uuid.UUID,
        *,
        now: datetime | None,
    ) -> tuple[
        list[Recommendation],
        dict[uuid.UUID, StoredArticle],
        dict[uuid.UUID, StoredPaper],
    ]:
        stored = self._profiles.get_by_id(profile_id)
        if stored is None:
            raise RecommendationProfileNotFoundError(profile_id)
        articles = {article.id: article for article in self._articles.list_accepted()}
        papers = {paper.id: paper for paper in self._papers.list_accepted()}
        contents = [recommendable_article(article) for article in articles.values()]
        contents.extend(recommendable_paper(paper) for paper in papers.values())
        ranked = recommend(
            domain_profile(stored),
            contents,
            now=now if now is not None else datetime.now(UTC),
        )
        return ranked, articles, papers
