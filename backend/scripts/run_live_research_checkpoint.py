"""Manual live arXiv → Research Agent → Quality Gate → Postgres checkpoint.

Not invoked by pytest. Makes real network and LLM calls.

From backend/:

  PYTHONPATH=. python scripts/run_live_research_checkpoint.py
"""

from app.config import get_settings
from app.db.schema import create_tables
from app.db.session import get_engine, get_session_factory
from app.domain.models import ResearchAnalysis
from app.ingestion.arxiv import DEFAULT_ARXIV_QUERY
from app.llm.lite import LiteLlmClient
from app.pipeline import ResearchIngestion, ResearchIngestionItemResult

MAX_RESULTS = 3


def _print_item_result(result: ResearchIngestionItemResult) -> None:
    if result.skipped:
        stored = result.stored
        print(f"arxiv_id:       {stored.arxiv_id if stored is not None else 'n/a'}")
        print(f"title:          {stored.title if stored is not None else 'n/a'}")
        print("skipped:        yes")
        print("status:         skipped")
        print()
        return

    item = result.item
    if item is None:
        print("arxiv_id:       n/a")
        print("title:          n/a")
        print("skipped:        no")
        print("status:         error")
        print("error:          missing pipeline item")
        print()
        return

    candidate = item.candidate
    print(f"arxiv_id:       {candidate.arxiv_id}")
    print(f"title:          {candidate.title}")
    print("skipped:        no")

    if item.error is not None:
        print("status:         error")
        print(f"error:          {item.error}")
        print()
        return

    analysis = item.analysis
    decision = item.decision
    print("status:         processed")
    print(f"category:       {analysis.category if analysis is not None else 'n/a'}")
    print(
        "relevance_score: "
        + (f"{analysis.relevance_score:.2f}" if analysis is not None else "n/a")
    )
    if decision is None:
        print("decision:       n/a")
    elif decision.accepted:
        print("decision:       accepted")
    else:
        print("decision:       rejected")
        print(f"quality_reason: {decision.reason or 'n/a'}")
    print()


def main() -> None:
    settings = get_settings()
    query = DEFAULT_ARXIV_QUERY
    print(f"model:       {settings.llm_model}")
    print(f"query:       {query}")
    print(f"max_results: {MAX_RESULTS}")
    print()

    llm = LiteLlmClient(
        model=settings.llm_model,
        json_schema=ResearchAnalysis.model_json_schema(),
        json_schema_name="research_analysis",
    )

    create_tables(get_engine())
    session = get_session_factory()()
    try:
        results = ResearchIngestion(llm).run(
            query,
            session,
            max_results=MAX_RESULTS,
        )
        print(f"result count: {len(results)}\n")

        processed = 0
        skipped = 0
        persisted = 0
        accepted = 0
        rejected = 0
        failed = 0
        for result in results:
            _print_item_result(result)
            if result.skipped:
                skipped += 1
                continue
            processed += 1
            item = result.item
            if item is None or item.error is not None:
                failed += 1
                continue
            if result.stored is not None:
                persisted += 1
            if item.decision is not None:
                if item.decision.accepted:
                    accepted += 1
                else:
                    rejected += 1

        print(f"processed: {processed}")
        print(f"skipped:   {skipped}")
        print(f"persisted: {persisted}")
        print(f"accepted:  {accepted}")
        print(f"rejected:  {rejected}")
        print(f"failed:    {failed}")
        session.commit()
        print("committed")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
