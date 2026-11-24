"""Find Python files in a repository and extract their functions.

`find_python_files` lists the files worth scanning. `walk_repo` runs the
extractor on each one and reports both the functions found and the files
that could not be read, so nothing is dropped silently.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from .python_extractor import extract_file

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

# Errors that mean "this one file can't be read", so the scan should go on.
# SyntaxError: invalid Python. ValueError: includes UnicodeDecodeError and
# null bytes. OSError: unreadable or vanished files. RecursionError and
# MemoryError: pathological files (very long expression chains, huge
# generated code) that overflow the parser. Deliberately NOT a bare
# `except Exception`, which would also hide bugs in our own code.
SKIPPABLE_ERRORS = (SyntaxError, ValueError, OSError, RecursionError, MemoryError)


@dataclass
class RepoScan:
    functions: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    modules: list[dict] = field(default_factory=list)


def find_python_files(folder: str | os.PathLike) -> list[str]:
    """Return a sorted list of POSIX-style relative paths to all .py files in folder.

    Raises FileNotFoundError if the folder is missing and NotADirectoryError
    if the path is a file. Files are listed, not parsed, so a broken .py
    file still appears here.
    """
    if not os.path.exists(folder):
        # Show the resolved path: it exposes relative-path mistakes that
        # the raw string you typed would hide.
        raise FileNotFoundError(f"Directory does not exist: {Path(folder).resolve()}")
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"Path is not a directory: {Path(folder).resolve()}")

    py_files = []

    for root, dirs, files in os.walk(folder):
        # Prune in place so os.walk never descends into junk folders
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

        # Wrap only extract_file so bugs in our own dict-building logic still crash loudly
        try:
            extracted, module_ranges = extract_file(full_path)
        except SKIPPABLE_ERRORS as exc:
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
        for module_range in module_ranges:
            scan.modules.append({"file": rel_path, **module_range})

    return scan
