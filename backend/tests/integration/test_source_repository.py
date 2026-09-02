import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.repositories.sources import (
    OPENAI_NEWS_NAME,
    OPENAI_NEWS_URL,
    SOURCE_TYPE_RSS,
    SourceRepository,
)

OTHER_URL = "https://example.com/rss.xml"


def test_sources_table_uses_postgres_types(postgres_engine: Engine) -> None:
    columns = {
        column["name"]: column
        for column in inspect(postgres_engine).get_columns("sources")
    }
    assert "UUID" in str(columns["id"]["type"]).upper()
    assert getattr(columns["created_at"]["type"], "timezone", False) is True
    assert getattr(columns["updated_at"]["type"], "timezone", False) is True
    unique_constraints = inspect(postgres_engine).get_unique_constraints("sources")
    unique_indexes = [
        tuple(index["column_names"])
        for index in inspect(postgres_engine).get_indexes("sources")
        if index["unique"]
    ]
    unique_names = {tuple(item["column_names"]) for item in unique_constraints}
    unique_names |= set(unique_indexes)
    assert ("url",) in unique_names


def test_upsert_inserts_then_updates_in_place(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    first = repo.upsert(
        name="Example Feed",
        url=OTHER_URL,
        source_type=SOURCE_TYPE_RSS,
        enabled=True,
    )
    second = repo.upsert(
        name="Renamed Feed",
        url=OTHER_URL,
        source_type="atom",
        enabled=False,
    )
    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.name == "Renamed Feed"
    assert second.url == OTHER_URL
    assert second.source_type == "atom"
    assert second.enabled is False
    assert second.updated_at >= first.updated_at
    assert repo.get_by_url(OTHER_URL) == second


def test_get_by_url_returns_none_when_missing(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    assert repo.get_by_url("https://example.com/missing.xml") is None


def test_list_enabled_excludes_disabled_and_orders_by_name(
    db_session: Session,
) -> None:
    repo = SourceRepository(db_session)
    repo.upsert(name="Zebra", url="https://example.com/zebra.xml")
    repo.upsert(name="Alpha", url="https://example.com/alpha.xml")
    repo.upsert(
        name="Muted",
        url="https://example.com/muted.xml",
        enabled=False,
    )
    enabled = repo.list_enabled()
    assert [source.name for source in enabled] == ["Alpha", "Zebra"]


def test_openai_news_seed_values_upsert(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    stored = repo.upsert(
        name=OPENAI_NEWS_NAME,
        url=OPENAI_NEWS_URL,
        source_type=SOURCE_TYPE_RSS,
        enabled=True,
    )
    assert stored.name == "OpenAI News"
    assert stored.url == OPENAI_NEWS_URL
    assert stored.source_type == "rss"
    assert stored.enabled is True


def test_non_rss_source_type_is_accepted(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    stored = repo.upsert(
        name="Docs",
        url="https://example.com/docs.xml",
        source_type="html",
    )
    assert stored.source_type == "html"


def test_blank_name_is_rejected(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    with pytest.raises(ValidationError):
        repo.upsert(name="   ", url=OTHER_URL)


def test_blank_source_type_is_rejected(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    with pytest.raises(ValidationError):
        repo.upsert(name="Example", url=OTHER_URL, source_type="  ")


def test_non_http_url_is_rejected(db_session: Session) -> None:
    repo = SourceRepository(db_session)
    with pytest.raises(ValidationError):
        repo.upsert(name="Example", url="not-a-url")
