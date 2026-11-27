from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ask_repo.storage.models import (
    Base,
    ChunkRecord,
    FileRecord,
    RepositoryRecord,
)


def test_repository_file_and_chunk_can_be_saved_and_loaded():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = RepositoryRecord(url="https://example.com/team/project")
        source_file = FileRecord(path="src/example.py")
        source_file.chunks.append(
            ChunkRecord(
                chunk_id="chunk-123",
                kind="function",
                name="answer",
                qualified_name="answer",
                start_line=3,
                end_line=5,
                text="def answer():\n    return 42",
                part=1,
                parts=1,
            )
        )
        repository.files.append(source_file)
        session.add(repository)
        session.commit()

        saved_chunk = session.scalar(select(ChunkRecord))
        assert saved_chunk.file.path == "src/example.py"
        assert saved_chunk.file.repository.url == "https://example.com/team/project"
        assert saved_chunk.start_line == 3
        assert saved_chunk.end_line == 5
        assert saved_chunk.text == "def answer():\n    return 42"
