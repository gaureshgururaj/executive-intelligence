import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.models import ArticleCandidate
from app.ingestion.errors import RssFetchError
from app.llm.errors import LlmClientError
from app.pipeline import FeedIngestion, FeedItemResult
from app.quality import QualityGate
from app.repositories.articles import StoredArticle

FEED_URL = "https://example.com/rss.xml"
NOW = datetime(2026, 8, 30, tzinfo=UTC)

ACCEPTED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/accepted",
    title="Accepted article",
    excerpt="Enough text for publication.",
    published_at=NOW,
)

REJECTED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/rejected",
    title="Rejected article",
    excerpt="Low relevance item.",
    published_at=NOW,
)

FAILED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/failed",
    title="Failed article",
    excerpt="This one will not parse.",
    published_at=NOW,
)

CHANGED = ArticleCandidate(
    source_url=FEED_URL,
    canonical_url="https://example.com/articles/changed",
    title="Changed article",
    excerpt="Original excerpt.",
    published_at=NOW,
)

ACCEPTED_JSON = json.dumps(
    {
        "summary": "This development matters for enterprise automation.",
        "category": "Agentic AI",
        "relevance_score": 0.9,
        "key_points": ["Enterprise automation", "Open tooling"],
    }
)

REJECTED_JSON = json.dumps(
    {
        "summary": "Minor product note with little strategic impact.",
        "category": "Other",
        "relevance_score": 0.2,
        "key_points": ["Minor product note"],
    }
)

CHANGED_JSON = json.dumps(
    {
        "summary": "The article was updated and needs a fresh briefing.",
        "category": "LLMs",
        "relevance_score": 0.7,
        "key_points": ["Updated coverage"],
    }
)


class MappingLlmClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.complete_calls = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.complete_calls += 1
        self.prompts.append(prompt)
        for url, response in self.responses.items():
            if url in prompt:
                return response
        raise AssertionError(f"no LLM fixture for prompt: {prompt}")


def _mapping_llm() -> MappingLlmClient:
    return MappingLlmClient(
        {
            ACCEPTED.canonical_url: ACCEPTED_JSON,
            REJECTED.canonical_url: REJECTED_JSON,
            FAILED.canonical_url: "not json",
            CHANGED.canonical_url: CHANGED_JSON,
        }
    )


def _stored(candidate: ArticleCandidate, *, accepted: bool) -> StoredArticle:
    return StoredArticle(
        id=uuid4(),
        source_url=str(candidate.source_url),
        canonical_url=str(candidate.canonical_url),
        title=candidate.title,
        excerpt=candidate.excerpt,
        published_at=candidate.published_at,
        summary="Existing summary",
        category="Existing",
        relevance_score=0.9 if accepted else 0.2,
        key_points=["Existing point"],
        accepted=accepted,
        quality_reason=None if accepted else "Relevance score below threshold",
        created_at=NOW,
        updated_at=NOW,
    )


def _run(
    candidates: list[ArticleCandidate],
    llm: MappingLlmClient | None = None,
    *,
    max_articles: int | None = None,
    known: dict[str, StoredArticle] | None = None,
) -> tuple[list[FeedItemResult], MagicMock, MagicMock, MappingLlmClient]:
    client = llm or _mapping_llm()
    session = MagicMock()
    repository = MagicMock()
    repository.get_by_canonical_urls.return_value = known or {}
    with (
        patch("app.pipeline.feed.ingest_rss", return_value=candidates),
        patch("app.repositories.articles.ArticleRepository", return_value=repository),
    ):
        results = FeedIngestion(client, quality_gate=QualityGate()).run(
            FEED_URL,
            session,
            max_articles=max_articles,
        )
    return results, session, repository, client


def test_save_called_for_accepted_and_rejected_not_for_failed() -> None:
    results, _, repository, _ = _run([ACCEPTED, REJECTED, FAILED])
    saved_items = [
        call.args[0] for call in repository.save_pipeline_item.call_args_list
    ]
    saved_urls = [str(item.candidate.canonical_url) for item in saved_items]

    assert repository.save_pipeline_item.call_count == 2
    assert saved_urls == [ACCEPTED.canonical_url, REJECTED.canonical_url]
    assert all(item.error is None for item in saved_items)
    assert saved_items[0].decision is not None and saved_items[0].decision.accepted
    assert saved_items[1].decision is not None and not saved_items[1].decision.accepted

    failed = results[2]
    assert failed.skipped is False
    assert failed.item is not None
    assert failed.item.error is not None
    assert failed.stored is None
    assert FAILED.canonical_url not in saved_urls


def test_max_articles_slices_before_lookup_and_llm() -> None:
    results, _, repository, llm = _run(
        [ACCEPTED, REJECTED, FAILED],
        max_articles=2,
    )
    assert llm.complete_calls == 2
    repository.get_by_canonical_urls.assert_called_once_with(
        [str(ACCEPTED.canonical_url), str(REJECTED.canonical_url)]
    )
    assert [result.item is not None for result in results] == [True, True]
    assert [str(result.item.candidate.canonical_url) for result in results] == [
        ACCEPTED.canonical_url,
        REJECTED.canonical_url,
    ]
    assert repository.save_pipeline_item.call_count == 2


def test_session_is_not_committed_rolled_back_or_closed() -> None:
    _, session, _, _ = _run([ACCEPTED])
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()


def test_rss_fetch_error_propagates_without_saving() -> None:
    session = MagicMock()
    repository = MagicMock()
    with (
        patch(
            "app.pipeline.feed.ingest_rss",
            side_effect=RssFetchError("Unparseable RSS feed"),
        ),
        patch("app.repositories.articles.ArticleRepository", return_value=repository),
        pytest.raises(RssFetchError, match="Unparseable RSS feed"),
    ):
        FeedIngestion(_mapping_llm()).run(FEED_URL, session)
    repository.get_by_canonical_urls.assert_not_called()
    repository.save_pipeline_item.assert_not_called()
    session.commit.assert_not_called()


def test_llm_client_error_is_not_persisted() -> None:
    class MixedLlmClient:
        def __init__(self) -> None:
            self.complete_calls = 0

        def complete(self, prompt: str) -> str:
            self.complete_calls += 1
            if FAILED.canonical_url in prompt:
                raise LlmClientError("LiteLLM completion failed for model test")
            if ACCEPTED.canonical_url in prompt:
                return ACCEPTED_JSON
            raise AssertionError(f"no LLM fixture for prompt: {prompt}")

    llm = MixedLlmClient()
    results, _, repository, _ = _run([ACCEPTED, FAILED], llm=llm)
    saved_urls = [
        str(call.args[0].candidate.canonical_url)
        for call in repository.save_pipeline_item.call_args_list
    ]
    assert llm.complete_calls == 2
    assert saved_urls == [ACCEPTED.canonical_url]
    assert results[1].skipped is False
    assert results[1].stored is None
    assert results[1].item is not None
    assert results[1].item.error == "LiteLLM completion failed for model test"


def test_unchanged_accepted_row_is_skipped_without_llm_or_save() -> None:
    stored = _stored(ACCEPTED, accepted=True)
    results, _, repository, llm = _run(
        [ACCEPTED],
        known={str(ACCEPTED.canonical_url): stored},
    )
    assert llm.complete_calls == 0
    repository.save_pipeline_item.assert_not_called()
    assert results == [
        FeedItemResult(item=None, stored=stored, skipped=True),
    ]


def test_unchanged_rejected_row_is_skipped_without_llm_or_save() -> None:
    stored = _stored(REJECTED, accepted=False)
    results, _, repository, llm = _run(
        [REJECTED],
        known={str(REJECTED.canonical_url): stored},
    )
    assert llm.complete_calls == 0
    repository.save_pipeline_item.assert_not_called()
    assert results[0].skipped is True
    assert results[0].item is None
    assert results[0].stored is stored
    assert results[0].stored is not None
    assert results[0].stored.accepted is False


def test_new_row_is_processed_normally() -> None:
    results, _, repository, llm = _run([ACCEPTED], known={})
    assert llm.complete_calls == 1
    assert repository.save_pipeline_item.call_count == 1
    assert results[0].skipped is False
    assert results[0].item is not None
    assert results[0].item.error is None


def test_changed_title_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(update={"title": "New title"})
    results, _, repository, llm = _run(
        [candidate],
        known={str(CHANGED.canonical_url): stored},
    )
    assert llm.complete_calls == 1
    assert repository.save_pipeline_item.call_count == 1
    assert results[0].skipped is False


def test_changed_excerpt_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(update={"excerpt": "New excerpt"})
    _, _, repository, llm = _run(
        [candidate],
        known={str(CHANGED.canonical_url): stored},
    )
    assert llm.complete_calls == 1
    assert repository.save_pipeline_item.call_count == 1


def test_changed_published_at_is_reprocessed() -> None:
    stored = _stored(CHANGED, accepted=True)
    candidate = CHANGED.model_copy(
        update={"published_at": datetime(2026, 9, 1, tzinfo=UTC)}
    )
    _, _, repository, llm = _run(
        [candidate],
        known={str(CHANGED.canonical_url): stored},
    )
    assert llm.complete_calls == 1
    assert repository.save_pipeline_item.call_count == 1


def test_mixed_known_new_and_changed_only_required_hit_llm() -> None:
    accepted_stored = _stored(ACCEPTED, accepted=True)
    changed_stored = _stored(CHANGED, accepted=True)
    changed = CHANGED.model_copy(update={"title": "Updated changed title"})
    results, _, repository, llm = _run(
        [ACCEPTED, REJECTED, changed],
        known={
            str(ACCEPTED.canonical_url): accepted_stored,
            str(CHANGED.canonical_url): changed_stored,
        },
    )
    assert llm.complete_calls == 2
    assert ACCEPTED.canonical_url not in "".join(llm.prompts)
    assert REJECTED.canonical_url in "".join(llm.prompts)
    assert CHANGED.canonical_url in "".join(llm.prompts)
    assert results[0].skipped is True
    assert results[0].item is None
    assert results[0].stored is accepted_stored
    assert results[1].skipped is False
    assert results[1].item is not None
    assert results[2].skipped is False
    assert results[2].item is not None
    assert [
        str(ACCEPTED.canonical_url),
        str(results[1].item.candidate.canonical_url),
        str(results[2].item.candidate.canonical_url),
    ] == [
        ACCEPTED.canonical_url,
        REJECTED.canonical_url,
        CHANGED.canonical_url,
    ]
    repository.get_by_canonical_urls.assert_called_once()


def test_missing_row_is_processed_again() -> None:
    results, _, repository, llm = _run([FAILED], known={})
    assert llm.complete_calls == 1
    assert repository.save_pipeline_item.call_count == 0
    assert results[0].skipped is False
    assert results[0].item is not None
    assert results[0].item.error is not None


def test_batch_lookup_happens_once() -> None:
    _, _, repository, _ = _run([ACCEPTED, REJECTED, FAILED])
    repository.get_by_canonical_urls.assert_called_once_with(
        [
            str(ACCEPTED.canonical_url),
            str(REJECTED.canonical_url),
            str(FAILED.canonical_url),
        ]
    )
    repository.get_by_canonical_url.assert_not_called()
