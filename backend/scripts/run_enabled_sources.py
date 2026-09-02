"""Ingest all enabled configured sources.

Not invoked by pytest. Makes real network and LLM calls.

From backend/:

  PYTHONPATH=. python scripts/run_enabled_sources.py
"""

from app.config import get_settings
from app.db.schema import create_tables
from app.db.session import get_engine, get_session_factory
from app.domain.models import TrendAnalysis
from app.llm.lite import LiteLlmClient
from app.pipeline import EnabledSourceIngestionRunner, FeedIngestion, SourceRunResult

MAX_ARTICLES = 3


def _print_source_result(result: SourceRunResult) -> None:
    status = "error" if result.error is not None else "ok"
    print(f"source:     {result.source_name}")
    print(f"url:        {result.source_url}")
    print(f"id:         {result.source_id}")
    print(f"status:     {status}")
    print(f"processed:  {result.processed}")
    print(f"persisted:  {result.persisted}")
    print(f"accepted:   {result.accepted}")
    print(f"rejected:   {result.rejected}")
    print(f"failed:     {result.failed}")
    print(f"detail:     {result.error or 'n/a'}")
    print()


def main() -> None:
    settings = get_settings()
    print(f"model: {settings.llm_model}")
    print(f"limit: {MAX_ARTICLES} candidates per source before any LLM call")
    print()

    llm = LiteLlmClient(
        model=settings.llm_model,
        json_schema=TrendAnalysis.model_json_schema(),
    )
    create_tables(get_engine())
    runner = EnabledSourceIngestionRunner(
        session_factory=get_session_factory(),
        ingestion=FeedIngestion(llm),
    )
    results = runner.run(max_articles=MAX_ARTICLES)
    print(f"enabled sources: {len(results)}\n")
    for result in results:
        _print_source_result(result)


if __name__ == "__main__":
    main()
