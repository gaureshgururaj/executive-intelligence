from app.domain.models import RecommendableContent
from app.repositories.articles import StoredArticle
from app.repositories.papers import StoredPaper


def _join_text(*parts: str | list[str]) -> str:
    lines: list[str] = []
    for part in parts:
        if isinstance(part, list):
            lines.extend(part)
        else:
            lines.append(part)
    return "\n".join(lines)


def recommendable_article(article: StoredArticle) -> RecommendableContent:
    return RecommendableContent(
        content_id=article.id,
        content_type="article",
        title=article.title,
        category=article.category,
        relevance_score=article.relevance_score,
        published_at=article.published_at,
        created_at=article.created_at,
        text=_join_text(
            article.category,
            article.title,
            article.summary,
            article.key_points,
        ),
    )


def recommendable_paper(paper: StoredPaper) -> RecommendableContent:
    return RecommendableContent(
        content_id=paper.id,
        content_type="paper",
        title=paper.title,
        category=paper.category,
        relevance_score=paper.relevance_score,
        published_at=paper.published_at,
        created_at=paper.created_at,
        text=_join_text(
            paper.category,
            paper.title,
            paper.summary,
            paper.key_findings,
            paper.practical_implications,
        ),
    )
