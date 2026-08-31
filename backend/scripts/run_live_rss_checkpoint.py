"""Manual live RSS → Trend Agent → Quality Gate → Postgres checkpoint.

Not invoked by pytest. Makes real network and LLM calls.

From backend/:

  PYTHONPATH=. python scripts/run_live_rss_checkpoint.py
"""

from app.config import get_settings
from app.db.schema import create_tables
from app.db.session import get_engine, get_session_factory
from app.domain.models import TrendAnalysis
from app.llm.lite import LiteLlmClient
from app.pipeline import FeedIngestion, FeedItemResult

DEFAULT_FEED_URL = "https://openai.com/news/rss.xml"
MAX_ARTICLES = 3


def _print_item_result(result: FeedItemResult) -> None:
    item = result.item
    candidate = item.candidate
    analysis_ok = item.error is None and item.analysis is not None
    analysis = item.analysis
    decision = item.decision
    if decision is None:
        verdict = "n/a"
        reason = item.error or "n/a"
    elif decision.accepted:
        verdict = "accepted"
        reason = decision.reason or "n/a"
    else:
        verdict = "rejected"
        reason = decision.reason or "n/a"
    category = analysis.category if analysis is not None else "n/a"
    score = f"{analysis.relevance_score:.2f}" if analysis is not None else "n/a"
    print(f"title:      {candidate.title}")
    print(f"analysis:   {'success' if analysis_ok else 'failure'}")
    print(f"category:   {category}")
    print(f"relevance:  {score}")
    print(f"decision:   {verdict}")
    print(f"detail:     {reason}")
    print(f"persisted:  {'yes' if result.stored is not None else 'no'}")
    print()


def main() -> None:
    settings = get_settings()
    feed_url = DEFAULT_FEED_URL
    print(f"feed:  {feed_url}")
    print(f"model: {settings.llm_model}")
    print(f"limit: {MAX_ARTICLES} candidates before any LLM call")
    print()

    llm = LiteLlmClient(
        model=settings.llm_model,
        json_schema=TrendAnalysis.model_json_schema(),
    )

    create_tables(get_engine())
    session = get_session_factory()()
    try:
        results = FeedIngestion(llm).run(
            feed_url,
            session,
            max_articles=MAX_ARTICLES,
        )
        print(f"processing {len(results)} candidate(s)\n")
        for result in results:
            _print_item_result(result)
        session.commit()
        print("committed")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
