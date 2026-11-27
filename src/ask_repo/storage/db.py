"""Create SQLAlchemy engines and session factories for storage."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(database_url: str) -> Engine:
    """Create the long-lived connection manager for a database URL."""
    if not database_url.strip():
        raise ValueError("database_url must not be empty")
    return create_engine(database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a reusable factory that opens short-lived database sessions."""
    return sessionmaker(bind=engine)
