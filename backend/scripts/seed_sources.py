"""Insert default RSS sources. Idempotent. Does not ingest.

Not invoked by pytest. Does not call the LLM.

From backend/:

  PYTHONPATH=. python scripts/seed_sources.py
"""

from app.db.schema import create_tables
from app.db.session import get_engine, get_session_factory
from app.repositories.sources import (
    OPENAI_NEWS_NAME,
    OPENAI_NEWS_URL,
    SOURCE_TYPE_RSS,
    SourceRepository,
)


def main() -> None:
    create_tables(get_engine())
    session = get_session_factory()()
    try:
        stored = SourceRepository(session).upsert(
            name=OPENAI_NEWS_NAME,
            url=OPENAI_NEWS_URL,
            source_type=SOURCE_TYPE_RSS,
            enabled=True,
        )
        session.commit()
        print(f"id:      {stored.id}")
        print(f"name:    {stored.name}")
        print(f"url:     {stored.url}")
        print(f"type:    {stored.source_type}")
        print(f"enabled: {stored.enabled}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
