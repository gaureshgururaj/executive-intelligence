from sqlalchemy.engine import Engine

from app.db.models import Article, Paper, Source
from app.db.session import Base


def create_tables(engine: Engine) -> None:
    """Create ORM tables. Models are imported so they are registered on Base."""
    _ = Article
    _ = Paper
    _ = Source
    Base.metadata.create_all(engine)
