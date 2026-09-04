"""Manual live recommendation checkpoint over persisted accepted content.

Not invoked by pytest. Does not call the LLM, arXiv, or RSS.

From backend/:

  PYTHONPATH=. python scripts/run_live_recommendation_checkpoint.py
"""

import uuid

from app.db.schema import create_tables
from app.db.session import get_engine, get_session_factory
from app.domain.models import Recommendation, RecommendationProfile
from app.recommendations.service import RecommendationService
from app.repositories import (
    ArticleRepository,
    PaperRepository,
    RecommendationProfileRepository,
)

DEMO_PROFILES = (
    RecommendationProfile(
        id=uuid.uuid4(),
        name="LLM & AI Strategy",
        interests=["GPT", "licensing", "cybersecurity", "startups"],
    ),
    RecommendationProfile(
        id=uuid.uuid4(),
        name="Research Systems",
        interests=["speech enhancement", "planning", "reinforcement learning"],
    ),
)


def _title_and_relevance(
    recommendation: Recommendation,
    articles: dict,
    papers: dict,
) -> tuple[str, float]:
    if recommendation.content_type == "article":
        item = articles[recommendation.content_id]
        return item.title, item.relevance_score
    item = papers[recommendation.content_id]
    return item.title, item.relevance_score


def _print_profile(
    name: str,
    interests: list[str],
    recommendations: list[Recommendation],
    articles: dict,
    papers: dict,
) -> None:
    print(f"PROFILE:\n{name}\n")
    print("INTERESTS:")
    for interest in interests:
        print(f"- {interest}")
    print()
    print("RECOMMENDATIONS:")
    if not recommendations:
        print("(none)")
        print()
        return
    for index, recommendation in enumerate(recommendations, start=1):
        title, relevance = _title_and_relevance(recommendation, articles, papers)
        matched = ", ".join(recommendation.matched_interests)
        print(f"{index}. [{recommendation.content_type}] {title}")
        print(f"   score: {recommendation.recommendation_score:.3f}")
        print(f"   relevance: {relevance:.2f}")
        print(f"   matched: {matched}")
        print(f"   reason: {recommendation.reason}")
        print()


def main() -> None:
    create_tables(get_engine())
    session = get_session_factory()()
    try:
        profiles = RecommendationProfileRepository(session)
        for profile in DEMO_PROFILES:
            profiles.save(profile)

        articles = {
            article.id: article
            for article in ArticleRepository(session).list_accepted()
        }
        papers = {paper.id: paper for paper in PaperRepository(session).list_accepted()}
        service = RecommendationService(session)

        print(f"articles_available: {len(articles)}")
        print(f"papers_available: {len(papers)}")
        print()

        for stored in profiles.list_all():
            if stored.name not in {profile.name for profile in DEMO_PROFILES}:
                continue
            recommendations = service.recommend_for_profile(stored.id)
            _print_profile(
                stored.name,
                stored.interests,
                recommendations,
                articles,
                papers,
            )
            print(f"recommendations_returned: {len(recommendations)}")
            print()

        session.commit()
        print("committed")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
