from sqlalchemy import select

from ask_repo.storage.db import create_db_engine, create_session_factory


def test_engine_uses_the_given_database_url():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")

    assert engine.url.drivername == "sqlite+pysqlite"

    engine.dispose()


def test_session_factory_opens_a_session_connected_to_its_engine():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        assert session.scalar(select(1)) == 1

    engine.dispose()
