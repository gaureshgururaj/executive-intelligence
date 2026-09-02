"""Ingest all enabled configured sources.

Not invoked by pytest. Makes real network and LLM calls.

From backend/:

  PYTHONPATH=. python scripts/run_enabled_sources.py

A host cron or hosted scheduler should invoke this same command. The scheduler
decides WHEN to run; this script decides HOW to construct dependencies and
WHAT to ingest. Source-level transaction behavior stays in
EnabledSourceIngestionRunner.
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.db.schema import create_tables
from app.db.session import get_engine, get_session_factory
from app.domain.models import TrendAnalysis
from app.llm.lite import LiteLlmClient
from app.pipeline import EnabledSourceIngestionRunner, FeedIngestion, SourceRunResult


def exit_code_for(results: list[SourceRunResult]) -> int:
    """Map completed source runs to a Unix process exit code.

    Zero enabled sources and completed source transactions exit 0, including
    item-level failures that the runner already committed. Any source-level
    error exits 1. Setup/discovery exceptions are not handled here and
    propagate as a non-zero process exit.
    """
    if any(result.error is not None for result in results):
        return 1
    return 0


def _print_source_result(result: SourceRunResult) -> None:
    status = "error" if result.error is not None else "ok"
    print(f"source:     {result.source_name}")
    print(f"url:        {result.source_url}")
    print(f"id:         {result.source_id}")
    print(f"status:     {status}")
    print(f"processed:  {result.processed}")
    print(f"skipped:    {result.skipped}")
    print(f"persisted:  {result.persisted}")
    print(f"accepted:   {result.accepted}")
    print(f"rejected:   {result.rejected}")
    print(f"failed:     {result.failed}")
    print(f"detail:     {result.error or 'n/a'}")
    print()


def main() -> int:
    settings = get_settings()
    print(f"model: {settings.llm_model}")
    print(
        f"limit: {settings.ingest_max_articles} candidates per source "
        "before any LLM call"
    )
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
    results = runner.run(max_articles=settings.ingest_max_articles)
    print(f"enabled sources: {len(results)}\n")
    for result in results:
        _print_source_result(result)
    return exit_code_for(results)


if __name__ == "__main__":
    sys.exit(main())
