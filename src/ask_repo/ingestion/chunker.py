"""Turn extracted Python functions into source chunks with citation metadata."""

from collections import defaultdict
from pathlib import Path

from .walker import walk_repo


def chunk_repo(root: str | Path) -> list[dict]:
    """Return one source chunk per function found in a repository.

    Each chunk keeps the repository-relative path and the extractor's inclusive
    line range. Files are read once here, regardless of how many functions they
    contain.
    """
    scan = walk_repo(root)
    functions_by_file = defaultdict(list)
    for function in scan.functions:
        functions_by_file[function["file"]].append(function)

    root_path = Path(root)
    chunks = []
    for rel_path, functions in functions_by_file.items():
        # Read once per file rather than reopening it for every function.
        lines = (root_path / rel_path).read_text(encoding="utf-8").splitlines()
        for function in functions:
            start = function["start_line"]
            end = function["end_line"]
            chunks.append({
                **function,
                "text": "\n".join(lines[start - 1 : end]),
            })

    return chunks
