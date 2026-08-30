from sqlalchemy.engine import Engine

from app.db.models import Article
from app.db.session import Base


def create_tables(engine: Engine) -> None:
    """Create ORM tables. Article is imported so it is registered on Base."""
    _ = Article
    Base.metadata.create_all(engine)
