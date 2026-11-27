from ask_repo.storage.db import create_db_engine


def test_engine_uses_the_given_database_url():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")

    assert engine.url.drivername == "sqlite+pysqlite"

    engine.dispose()
