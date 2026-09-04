import uuid
from datetime import UTC, datetime

from app.domain.models import RecommendationProfile
from app.recommendations.project import recommendable_article, recommendable_paper
from app.recommendations.service import domain_profile
from app.repositories.articles import StoredArticle
from app.repositories.papers import StoredPaper
from app.repositories.recommendation_profiles import StoredRecommendationProfile

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
ARTICLE_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
PAPER_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")


def _article(**overrides: object) -> StoredArticle:
    payload: dict[str, object] = {
        "id": ARTICLE_ID,
        "source_url": "https://example.com/feed-zzsourcezz.xml",
        "canonical_url": "https://example.com/articles/zzcanonicalzz",
        "title": "Accepted article title",
        "excerpt": "Excerpt should not be required in match text.",
        "published_at": NOW,
        "summary": "A summary about enterprise agents.",
        "category": "Agentic AI",
        "relevance_score": 0.82,
        "key_points": ["Open framework released", "Aimed at enterprise workflows"],
        "accepted": True,
        "quality_reason": "SECRET_QUALITY_REASON",
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return StoredArticle.model_validate(payload)


def _paper(**overrides: object) -> StoredPaper:
    payload: dict[str, object] = {
        "id": PAPER_ID,
        "arxiv_id": "9999.99999",
        "title": "Accepted paper title",
        "abstract": "UNIQUE_ABSTRACT_TOKEN_SHOULD_NOT_APPEAR",
        "authors": ["Ada Lovelace"],
        "published_at": NOW,
        "arxiv_updated_at": NOW,
        "paper_url": "http://arxiv.org/abs/zzpaperurlzz",
        "pdf_url": "http://arxiv.org/pdf/zzpdfurlzz",
        "categories": ["cs.ZZ"],
        "summary": "A summary about speech enhancement.",
        "category": "Speech Enhancement",
        "relevance_score": 0.7,
        "key_findings": ["Continuous representations outperform discrete tokens"],
        "practical_implications": ["Leaders can deploy flexible decoding policies"],
        "accepted": True,
        "quality_reason": "SECRET_PAPER_REASON",
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return StoredPaper.model_validate(payload)


def test_domain_profile_uses_persisted_id_name_and_interests() -> None:
    stored = StoredRecommendationProfile(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Applied LLMs",
        interests=["GPT", "licensing"],
        created_at=NOW,
        updated_at=NOW,
    )
    profile = domain_profile(stored)
    assert profile == RecommendationProfile(
        id=stored.id,
        name="Applied LLMs",
        interests=["GPT", "licensing"],
    )


def test_article_projection_includes_match_fields() -> None:
    content = recommendable_article(_article())
    assert content.content_id == ARTICLE_ID
    assert content.content_type == "article"
    assert content.title == "Accepted article title"
    assert content.category == "Agentic AI"
    assert content.relevance_score == 0.82
    assert content.published_at == NOW
    assert content.created_at == NOW
    assert "Agentic AI" in content.text
    assert "Accepted article title" in content.text
    assert "A summary about enterprise agents." in content.text
    assert "Open framework released" in content.text
    assert "Aimed at enterprise workflows" in content.text


def test_article_projection_excludes_persistence_fields() -> None:
    text = recommendable_article(_article()).text
    assert "zzcanonicalzz" not in text
    assert "zzsourcezz" not in text
    assert "SECRET_QUALITY_REASON" not in text
    assert "Excerpt should not be required in match text." not in text


def test_paper_projection_includes_match_fields() -> None:
    content = recommendable_paper(_paper())
    assert content.content_id == PAPER_ID
    assert content.content_type == "paper"
    assert "Speech Enhancement" in content.text
    assert "Accepted paper title" in content.text
    assert "A summary about speech enhancement." in content.text
    assert "Continuous representations outperform discrete tokens" in content.text
    assert "Leaders can deploy flexible decoding policies" in content.text


def test_paper_projection_excludes_abstract_and_arxiv_metadata() -> None:
    text = recommendable_paper(_paper()).text
    assert "UNIQUE_ABSTRACT_TOKEN_SHOULD_NOT_APPEAR" not in text
    assert "9999.99999" not in text
    assert "cs.ZZ" not in text
    assert "zzpaperurlzz" not in text
    assert "zzpdfurlzz" not in text
    assert "SECRET_PAPER_REASON" not in text
    assert "Ada Lovelace" not in text
