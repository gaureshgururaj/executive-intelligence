from datetime import datetime

from app.domain.models import (
    RecommendableContent,
    Recommendation,
    RecommendationProfile,
)
from app.recommendations.text import tokenize

PREFERENCE_WEIGHT = 0.55
RELEVANCE_WEIGHT = 0.30
RECENCY_WEIGHT = 0.15
RECENCY_WINDOW_DAYS = 90.0
_SECONDS_PER_DAY = 86400.0


def recommend(
    profile: RecommendationProfile,
    contents: list[RecommendableContent],
    *,
    now: datetime,
) -> list[Recommendation]:
    """Rank matching content for a profile. Unmatched items are omitted."""
    if not profile.interests:
        return []

    ranked: list[tuple[Recommendation, RecommendableContent]] = []
    for content in contents:
        matched = _matched_interests(profile.interests, content.text)
        if not matched:
            continue
        ranked.append(
            (
                Recommendation(
                    content_id=content.content_id,
                    content_type=content.content_type,
                    recommendation_score=_score(profile, content, matched, now),
                    matched_interests=matched,
                    reason=_format_reason(matched),
                ),
                content,
            )
        )
    ranked.sort(key=_sort_key)
    return [item for item, _ in ranked]


def _matched_interests(interests: list[str], text: str) -> list[str]:
    content_tokens = set(tokenize(text))
    matched: list[str] = []
    for interest in interests:
        interest_tokens = tokenize(interest)
        if not interest_tokens:
            continue
        if all(token in content_tokens for token in interest_tokens):
            matched.append(interest)
    return matched


def _score(
    profile: RecommendationProfile,
    content: RecommendableContent,
    matched_interests: list[str],
    now: datetime,
) -> float:
    preference_strength = len(matched_interests) / len(profile.interests)
    recency = _recency_component(content, now)
    score = (
        PREFERENCE_WEIGHT * preference_strength
        + RELEVANCE_WEIGHT * content.relevance_score
        + RECENCY_WEIGHT * recency
    )
    return min(1.0, max(0.0, score))


def _recency_component(content: RecommendableContent, now: datetime) -> float:
    timestamp = _effective_timestamp(content)
    age_days = (now - timestamp).total_seconds() / _SECONDS_PER_DAY
    return min(1.0, max(0.0, 1.0 - age_days / RECENCY_WINDOW_DAYS))


def _effective_timestamp(content: RecommendableContent) -> datetime:
    if content.published_at is not None:
        return content.published_at
    return content.created_at


def _format_reason(matched_interests: list[str]) -> str:
    if len(matched_interests) == 1:
        return f"Matches your interest in {matched_interests[0]}"
    if len(matched_interests) == 2:
        return (
            "Matches your interests in "
            f"{matched_interests[0]} and {matched_interests[1]}"
        )
    head = ", ".join(matched_interests[:-1])
    return f"Matches your interests in {head}, and {matched_interests[-1]}"


def _sort_key(
    pair: tuple[Recommendation, RecommendableContent],
) -> tuple[float, float, float, str, object]:
    recommendation, content = pair
    timestamp = _effective_timestamp(content)
    return (
        -recommendation.recommendation_score,
        -content.relevance_score,
        -timestamp.timestamp(),
        content.content_type,
        content.content_id,
    )
