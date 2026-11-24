"""Given a folder, return a sorted list of paths to every .py file inside it, 
relative to that folder, skipping junk folders."""

import os
from pathlib import Path
from .python_extractor import extract_functions
from dataclasses import dataclass, field


# Conservative v1 skip list: unambiguous tool, cache, and dependency folders only.
# Ambiguous names (like "build", "dist", "env") and hidden folders (like ".github")
# are intentionally omitted from this skip list so real source code is never silently dropped.

JUNK_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "node_modules",
}


@dataclass
class RepoScan:
    functions: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def find_python_files(folder: str | os.PathLike) -> list[str]:
    """Return a sorted list of POSIX-style relative paths to all .py files in folder."""
    if not os.path.exists(folder):
        raise FileNotFoundError(f"Directory does not exist: {folder}")
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"Path is not a directory: {folder}")

    py_files = []

    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in JUNK_DIRS]

        for filename in files:
            if filename.endswith(".py"):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, folder)
                py_files.append(Path(rel_path).as_posix())

    return sorted(py_files)


def walk_repo(root: str | os.PathLike) -> RepoScan:
    """Walk a repository, extract functions from all Python files, and record unreadable files."""
    rel_paths = find_python_files(root)
    root_path = Path(root)
    scan = RepoScan()

    for rel_path in rel_paths:
        full_path = root_path / rel_path

        # Wrap only extract_functions so bugs in our own dict-building logic still crash loudly
        try:
            extracted = extract_functions(full_path)
        except (SyntaxError, ValueError, OSError) as exc:
            scan.skipped.append(
                {
                    "file": rel_path,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue

        for fn in extracted:
            scan.functions.append({"file": rel_path, **fn})

    return scan
