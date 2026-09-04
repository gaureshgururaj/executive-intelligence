import uuid
from datetime import UTC, datetime, timedelta

from app.domain.models import RecommendableContent, RecommendationProfile
from app.recommendations import recommend
from app.recommendations.scoring import (
    PREFERENCE_WEIGHT,
    RECENCY_WEIGHT,
    RECENCY_WINDOW_DAYS,
    RELEVANCE_WEIGHT,
)
from app.recommendations.text import tokenize

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
CREATED = NOW - timedelta(days=10)


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-{n:012d}")


def _profile(**overrides: object) -> RecommendationProfile:
    payload: dict[str, object] = {
        "id": _id(1),
        "name": "Applied LLMs",
        "interests": ["language models"],
    }
    payload.update(overrides)
    return RecommendationProfile.model_validate(payload)


def _content(**overrides: object) -> RecommendableContent:
    payload: dict[str, object] = {
        "content_id": _id(10),
        "content_type": "article",
        "title": "Language models at work",
        "category": "LLMs",
        "relevance_score": 0.8,
        "published_at": CREATED,
        "created_at": CREATED,
        "text": "Language models at work",
    }
    payload.update(overrides)
    return RecommendableContent.model_validate(payload)


def test_tokenize_lowercases_and_drops_stopwords() -> None:
    assert tokenize("The Language of Models") == ["language", "models"]


def test_tokenize_preserves_short_technical_tokens() -> None:
    assert tokenize("AI and ML for RAG") == ["ai", "ml", "rag"]


def test_empty_interests_return_no_recommendations() -> None:
    assert recommend(_profile(interests=[]), [_content()], now=NOW) == []


def test_empty_corpus_returns_no_recommendations() -> None:
    assert recommend(_profile(), [], now=NOW) == []


def test_one_matching_interest_returns_the_item() -> None:
    results = recommend(_profile(), [_content()], now=NOW)
    assert len(results) == 1
    assert results[0].content_id == _id(10)
    assert results[0].matched_interests == ["language models"]


def test_nonmatching_item_is_omitted() -> None:
    other = _content(
        content_id=_id(11),
        title="Payroll software",
        text="Payroll software for finance teams",
    )
    results = recommend(_profile(), [_content(), other], now=NOW)
    assert [item.content_id for item in results] == [_id(10)]


def test_multi_token_phrase_requires_all_tokens() -> None:
    partial = _content(text="New language tooling shipped")
    assert recommend(_profile(), [partial], now=NOW) == []
    full = _content(text="New language models shipped")
    assert len(recommend(_profile(), [full], now=NOW)) == 1


def test_stopwords_do_not_prevent_a_phrase_match() -> None:
    content = _content(text="A review of the language of models")
    results = recommend(
        _profile(interests=["the language of models"]), [content], now=NOW
    )
    assert len(results) == 1


def test_stopword_only_interest_does_not_match() -> None:
    assert recommend(_profile(interests=["the and of"]), [_content()], now=NOW) == []


def test_matching_is_case_insensitive() -> None:
    content = _content(text="LANGUAGE MODELS at work")
    results = recommend(_profile(interests=["Language Models"]), [content], now=NOW)
    assert len(results) == 1


def test_multiple_matching_interests_increase_preference_strength() -> None:
    text = "Language models and speech enhancement in production"
    one = _profile(interests=["language models", "planning"])
    two = _profile(id=_id(2), name="Both", interests=["language models", "speech"])
    content = _content(text=text)
    one_match = recommend(one, [content], now=NOW)[0]
    two_match = recommend(two, [content], now=NOW)[0]
    assert two_match.recommendation_score > one_match.recommendation_score
    assert two_match.matched_interests == ["language models", "speech"]


def test_relevance_breaks_ties_when_preference_match_is_equal() -> None:
    low = _content(content_id=_id(10), relevance_score=0.4, text="language models")
    high = _content(content_id=_id(11), relevance_score=0.9, text="language models")
    results = recommend(_profile(), [low, high], now=NOW)
    assert [item.content_id for item in results] == [_id(11), _id(10)]
    assert results[0].recommendation_score > results[1].recommendation_score


def test_recency_breaks_ties_when_other_inputs_are_equal() -> None:
    older = _content(
        content_id=_id(10),
        published_at=NOW - timedelta(days=40),
        created_at=NOW - timedelta(days=40),
        text="language models",
        relevance_score=0.8,
    )
    newer = _content(
        content_id=_id(11),
        published_at=NOW - timedelta(days=2),
        created_at=NOW - timedelta(days=2),
        text="language models",
        relevance_score=0.8,
    )
    results = recommend(_profile(), [older, newer], now=NOW)
    assert [item.content_id for item in results] == [_id(11), _id(10)]


def test_content_older_than_90_days_gets_recency_zero() -> None:
    stale = _content(
        published_at=NOW - timedelta(days=91),
        created_at=NOW - timedelta(days=91),
        relevance_score=0.0,
        text="language models",
    )
    result = recommend(_profile(), [stale], now=NOW)[0]
    expected = PREFERENCE_WEIGHT * 1.0
    assert result.recommendation_score == expected


def test_future_timestamps_cap_recency_at_one() -> None:
    future = _content(
        published_at=NOW + timedelta(days=10),
        created_at=NOW + timedelta(days=10),
        relevance_score=0.0,
        text="language models",
    )
    result = recommend(_profile(), [future], now=NOW)[0]
    expected = PREFERENCE_WEIGHT * 1.0 + RECENCY_WEIGHT * 1.0
    assert result.recommendation_score == expected


def test_published_at_is_preferred_over_created_at_for_recency() -> None:
    content = _content(
        published_at=NOW - timedelta(days=5),
        created_at=NOW - timedelta(days=80),
        relevance_score=0.0,
        text="language models",
    )
    result = recommend(_profile(), [content], now=NOW)[0]
    recency = max(0.0, 1.0 - 5 / RECENCY_WINDOW_DAYS)
    expected = PREFERENCE_WEIGHT * 1.0 + RECENCY_WEIGHT * recency
    assert result.recommendation_score == expected


def test_article_and_paper_content_types_are_supported() -> None:
    article = _content(
        content_id=_id(10), content_type="article", text="language models"
    )
    paper = _content(content_id=_id(11), content_type="paper", text="language models")
    results = recommend(_profile(), [article, paper], now=NOW)
    types = {item.content_id: item.content_type for item in results}
    assert types[_id(10)] == "article"
    assert types[_id(11)] == "paper"


def test_two_profiles_rank_the_same_corpus_differently() -> None:
    language = _content(
        content_id=_id(10),
        content_type="article",
        title="Language models at work",
        text="Language models at work",
        relevance_score=0.9,
    )
    speech = _content(
        content_id=_id(11),
        content_type="paper",
        title="Speech enhancement methods",
        text="Speech enhancement methods",
        relevance_score=0.9,
    )
    mixed = _content(
        content_id=_id(12),
        title="Language models for speech enhancement",
        text="Language models for speech enhancement",
        relevance_score=0.5,
    )
    corpus = [language, speech, mixed]
    profile_a = _profile(name="Language", interests=["language models"])
    profile_b = _profile(id=_id(2), name="Speech", interests=["speech enhancement"])
    ranked_a = recommend(profile_a, corpus, now=NOW)
    ranked_b = recommend(profile_b, corpus, now=NOW)
    assert [item.content_id for item in ranked_a] == [_id(10), _id(12)]
    assert [item.content_id for item in ranked_b] == [_id(11), _id(12)]


def test_deterministic_tie_breaking_uses_type_then_id() -> None:
    shared = {
        "relevance_score": 0.8,
        "published_at": CREATED,
        "created_at": CREATED,
        "text": "language models",
    }
    later_article = _content(content_id=_id(30), content_type="article", **shared)
    paper = _content(content_id=_id(20), content_type="paper", **shared)
    earlier_article = _content(content_id=_id(10), content_type="article", **shared)
    results = recommend(_profile(), [later_article, paper, earlier_article], now=NOW)
    assert [item.content_id for item in results] == [_id(10), _id(30), _id(20)]
    assert [item.content_type for item in results] == ["article", "article", "paper"]


def test_score_remains_between_zero_and_one() -> None:
    content = _content(
        relevance_score=1.0,
        published_at=NOW + timedelta(days=1),
        created_at=NOW + timedelta(days=1),
        text="language models and speech",
    )
    profile = _profile(interests=["language models", "speech"])
    score = recommend(profile, [content], now=NOW)[0].recommendation_score
    assert 0.0 <= score <= 1.0
    expected = PREFERENCE_WEIGHT * 1.0 + RELEVANCE_WEIGHT * 1.0 + RECENCY_WEIGHT * 1.0
    assert score == expected


def test_reason_for_one_matched_interest() -> None:
    result = recommend(_profile(), [_content()], now=NOW)[0]
    assert result.reason == "Matches your interest in language models"


def test_reason_for_two_matched_interests() -> None:
    content = _content(text="Language models and speech enhancement")
    profile = _profile(interests=["language models", "speech"])
    result = recommend(profile, [content], now=NOW)[0]
    assert result.reason == "Matches your interests in language models and speech"


def test_reason_for_more_than_two_matched_interests() -> None:
    content = _content(text="Language models speech planning research")
    profile = _profile(interests=["language models", "speech", "planning"])
    result = recommend(profile, [content], now=NOW)[0]
    assert result.reason == (
        "Matches your interests in language models, speech, and planning"
    )


def test_same_inputs_and_now_produce_identical_output() -> None:
    corpus = [
        _content(content_id=_id(10), text="language models"),
        _content(content_id=_id(11), text="unrelated payroll"),
        _content(
            content_id=_id(12),
            content_type="paper",
            text="language models speech",
        ),
    ]
    profile = _profile(interests=["language models", "speech"])
    first = recommend(profile, corpus, now=NOW)
    second = recommend(profile, corpus, now=NOW)
    assert first == second
