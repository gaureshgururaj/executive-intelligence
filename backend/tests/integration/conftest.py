from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Article
from app.db.schema import create_tables


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("PostgreSQL is not available")
    create_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, autocommit=False)
    session.execute(delete(Article))
    session.flush()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
