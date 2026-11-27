import pytest

from ask_repo.config import Settings


def test_settings_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    settings = Settings.from_env()

    assert settings.database_url == "sqlite+pysqlite:///:memory:"


def test_settings_rejects_a_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_env()


def test_settings_repr_does_not_show_database_url():
    settings = Settings(database_url="postgresql+psycopg://user:secret@localhost/db")

    assert "secret" not in repr(settings)
