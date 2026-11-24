"""Turn extracted Python functions into source chunks with citation metadata."""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .walker import walk_repo


@dataclass
class ChunkResult:
    """Chunks produced from a repository and files the scan could not parse."""

    chunks: list[dict]
    skipped: list[dict]


def chunk_repo_detailed(root: str | Path) -> ChunkResult:
    """Return function and module chunks together with scan diagnostics.

    Function chunks preserve the extractor's inclusive line ranges. Module
    chunks contain consecutive top-level statements outside functions/classes,
    such as imports and constants. Each source file is read once while chunks
    are assembled.
    """
    scan = walk_repo(root)
    functions_by_file = defaultdict(list)
    for function in scan.functions:
        functions_by_file[function["file"]].append(function)
    modules_by_file = defaultdict(list)
    for module_range in scan.modules:
        modules_by_file[module_range["file"]].append(module_range)

    root_path = Path(root)
    chunks = []
    rel_paths = sorted(set(functions_by_file) | set(modules_by_file))
    for rel_path in rel_paths:
        # Read once per source file, regardless of its number of chunks.
        lines = (root_path / rel_path).read_text(encoding="utf-8").splitlines()

        for function in functions_by_file[rel_path]:
            start = function["start_line"]
            end = function["end_line"]
            chunks.append({
                **function,
                "kind": "function",
                "text": "\n".join(lines[start - 1 : end]),
            })

        for module_range in modules_by_file[rel_path]:
            start = module_range["start_line"]
            end = module_range["end_line"]
            chunks.append({
                "file": rel_path,
                "name": "<module>",
                "qualified_name": "<module>",
                "kind": "module",
                "start_line": start,
                "end_line": end,
                "text": "\n".join(lines[start - 1 : end]),
            })

    # Keep a predictable source order within and across files.
    chunks.sort(key=lambda chunk: (chunk["file"], chunk["start_line"]))

    return ChunkResult(chunks=chunks, skipped=scan.skipped)


def chunk_repo(root: str | Path) -> list[dict]:
    """Return function and module source chunks found in a repository.

    Use :func:`chunk_repo_detailed` when skipped-file diagnostics are needed.
    """
    return chunk_repo_detailed(root).chunks
