"""Database tables for repositories, source files, and code chunks."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class that collects the tables used by SQLAlchemy."""


class RepositoryRecord(Base):
    """One indexed repository revision."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[str | None] = mapped_column(String(64))

    files: Mapped[list[FileRecord]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class FileRecord(Base):
    """A repository-relative source file that contains stored chunks."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("repository_id", "path", name="uq_files_repository_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)

    repository: Mapped[RepositoryRecord] = relationship(back_populates="files")
    chunks: Mapped[list[ChunkRecord]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
    )


class ChunkRecord(Base):
    """A code chunk plus the source location needed to cite it."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("file_id", "chunk_id", name="uq_chunks_file_chunk_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    qualified_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_line: Mapped[int] = mapped_column(nullable=False)
    end_line: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    part: Mapped[int] = mapped_column(nullable=False)
    parts: Mapped[int] = mapped_column(nullable=False)

    file: Mapped[FileRecord] = relationship(back_populates="chunks")
