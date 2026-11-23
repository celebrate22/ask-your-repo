"""Given a folder, return a sorted list of paths to every .py file inside it, 
relative to that folder, skipping junk folders."""
import os
from pathlib import Path

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


def find_python_files(folder: str) -> list[str]:
    """Return a sorted list of POSIX-style relative paths to all .py files in folder."""
    if not os.path.exists(folder):
        raise FileNotFoundError(f"Directory does not exist: {folder}")
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"Path is not a directory: {folder}")

    py_files = []

    for root, dirs, files in os.walk(folder):
        # Prune unambiguous junk folders in-place so os.walk does not traverse them
        dirs[:] = [d for d in dirs if d not in JUNK_DIRS]

        for filename in files:
            if filename.endswith(".py"):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, folder)
                py_files.append(Path(rel_path).as_posix())

    return sorted(py_files)
