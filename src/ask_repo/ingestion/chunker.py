"""Turn Python source into chunks: pieces of code with citation metadata.

Three kinds of chunk cover the whole file's meaningful code:
  function  every function and method, at any nesting depth
  class     a class header plus its docstring, if any
  module    runs of consecutive top-level statements that are not
            definitions (imports, constants, `if __name__ == ...` blocks)

Each chunk's text is cut from the very same source string that was parsed,
so a chunk's text always matches its cited line range exactly.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import ast

from .python_extractor import QualifiedFunctionVisitor, parse_source, read_source
from .walker import SKIPPABLE_ERRORS, find_python_files

DEFAULT_MAX_LINES = 150

# Python's parser counts only these as line breaks. str.splitlines() also
# splits on form feeds, U+2028 and others, which would shift every later
# line number and cut the wrong text.
_LINE_BREAK = re.compile(r"\r\n|\r|\n")

_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True)
class Chunk:
    id: str                  # stable: same code -> same id (see _make_id)
    path: str                # repo-relative, POSIX separators
    kind: str                # "function", "class" or "module"
    name: str
    qualified_name: str      # e.g. "A.B.deep", "<module>"
    start_line: int          # 1-based, inclusive
    end_line: int            # 1-based, inclusive
    text: str                # exact source lines, "\n"-joined, no trailing newline
    part: int = 1            # a long chunk is split into parts: 1..parts
    parts: int = 1

    @property
    def search_text(self) -> str:
        """What to embed or keyword-search: the code plus where it lives.

        `text` stays pure source so it always matches the cited lines. The
        location header lets a search for a file or function name find it.
        """
        return f"{self.path} :: {self.qualified_name}\n{self.text}"


@dataclass
class ChunkScan:
    chunks: list[Chunk] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


class _SymbolVisitor(QualifiedFunctionVisitor):
    """The extractor's visitor, extended to also record classes."""

    def __init__(self):
        super().__init__()
        self.classes = []

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        try:
            self.classes.append((".".join(self.scope), node))
            self.generic_visit(node)
        finally:
            self.scope.pop()


def _start_line(node):
    """First line of a definition, counting decorators."""
    decorators = getattr(node, "decorator_list", [])
    return min([node.lineno] + [d.lineno for d in decorators])


def _is_docstring(node):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _class_range(node):
    """Lines of a class header plus its docstring (if it has one)."""
    start = _start_line(node)
    first = node.body[0]
    if _is_docstring(first):
        return start, first.end_lineno
    # Header only: up to the line before the body starts. A one-line
    # `class A: pass` has no such line, so it is just the class line.
    return start, max(node.lineno, _start_line(first) - 1)


def _module_ranges(tree):
    """Line ranges of consecutive top-level statements that aren't definitions."""
    ranges, run = [], []
    for node in tree.body + [None]:  # None flushes the final run
        if node is not None and not isinstance(node, _DEFINITIONS):
            run.append(node)
            continue
        if run:
            ranges.append((run[0].lineno, run[-1].end_lineno))
            run = []
    return ranges


def _make_id(path, kind, qualified_name, part, text):
    """Content-based id: independent of line numbers.

    Adding a line above a function shifts its line numbers but not its id,
    so re-indexing can tell "unchanged" from "changed" and skip re-embedding.
    """
    key = f"{path}\0{kind}\0{qualified_name}\0{part}\0{text}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def make_chunks(path: str, source: str, *, max_lines: int = DEFAULT_MAX_LINES) -> list[Chunk]:
    """Return all chunks of one Python source string, in file order.

    Raises SyntaxError if the source can't be parsed (RecursionError and
    MemoryError are possible for pathological input). Nothing is swallowed:
    the caller decides what to do about a broken file.

    Chunks longer than `max_lines` are split into consecutive parts of at
    most `max_lines` lines, each keeping its own exact line range.
    """
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")

    tree = parse_source(source, filename=path)
    lines = _LINE_BREAK.split(source)

    visitor = _SymbolVisitor()
    visitor.visit(tree)

    ranges = []  # (kind, name, qualified_name, start, end)
    for fn in visitor.results:
        ranges.append(("function", fn["name"], fn["qualified_name"], fn["start_line"], fn["end_line"]))
    for qualified_name, node in visitor.classes:
        start, end = _class_range(node)
        ranges.append(("class", node.name, qualified_name, start, end))
    for start, end in _module_ranges(tree):
        ranges.append(("module", "<module>", "<module>", start, end))

    # Stable, readable order: by position, outer before inner
    ranges.sort(key=lambda r: (r[3], -r[4], r[2]))

    chunks, seen_ids = [], {}
    for kind, name, qualified_name, start, end in ranges:
        total = -(-(end - start + 1) // max_lines)  # ceiling division
        for index in range(total):
            part_start = start + index * max_lines
            part_end = min(end, part_start + max_lines - 1)
            text = "\n".join(lines[part_start - 1 : part_end])
            chunk_id = _make_id(path, kind, qualified_name, index + 1, text)
            # Identical code defined twice (say in both branches of an if)
            # would collide; number the repeats so ids stay unique.
            seen_ids[chunk_id] = seen_ids.get(chunk_id, 0) + 1
            if seen_ids[chunk_id] > 1:
                chunk_id = f"{chunk_id}-{seen_ids[chunk_id]}"
            chunks.append(Chunk(
                id=chunk_id, path=path, kind=kind, name=name,
                qualified_name=qualified_name, start_line=part_start,
                end_line=part_end, text=text, part=index + 1, parts=total,
            ))
    return chunks


def chunk_repo(root: str | Path, *, max_lines: int = DEFAULT_MAX_LINES) -> ChunkScan:
    """Chunk every Python file under `root`; report the files that couldn't be read.

    Each file is read and parsed exactly once, here. (walk_repo is a separate
    scan; chunk_repo does not depend on it.) Raises FileNotFoundError or
    NotADirectoryError for a bad `root`.
    """
    result = ChunkScan()
    for rel_path in find_python_files(root):
        try:
            source = read_source(Path(root) / rel_path)
            chunks = make_chunks(rel_path, source, max_lines=max_lines)
        except SKIPPABLE_ERRORS as exc:
            result.skipped.append(
                {"file": rel_path, "error_type": type(exc).__name__, "message": str(exc)}
            )
            continue
        result.chunks.extend(chunks)
    return result