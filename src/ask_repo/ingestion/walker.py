"""Given a folder, return a sorted list of paths to every .py file inside it, 
relative to that folder, skipping junk folders."""

import os

JUNK_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".tox",
}

def walker(folder: str) -> list[str]:
    
    py_files = []

    for root, dirs, files in os.walk(folder):
        # Modify dirs in-place so os.walk skips junk and hidden folders completely
        dirs[:] = [d for d in dirs if d not in JUNK_DIRS and not d.startswith(".")]

        for filename in files:
            if filename.endswith(".py"):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, folder)
                py_files.append(rel_path)

    return sorted(py_files)
