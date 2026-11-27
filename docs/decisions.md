# Decisions

Short notes on implementation choices, why they were made, and what might
change them.

## Syntax errors raise in the extractor
`extract_functions_from_source` raises `SyntaxError` for invalid Python.
`walk_repo` and `chunk_repo` catch only the explicit `SKIPPABLE_ERRORS` list and
report the file, error type, and message. An empty extraction result therefore
means valid source with no functions.

## Scan errors are an explicit list
`SKIPPABLE_ERRORS` includes syntax, decoding/value, filesystem, recursion, and
parser-memory failures. A bare `except Exception` would hide bugs in our own
code. A `MemoryError` can still indicate process-wide memory pressure, so its
recorded message must remain visible.

## Scanned-code warnings are silenced during parsing
Only the AST parse call is wrapped in `warnings.catch_warnings()`. This keeps
warnings from untrusted repository code out of normal output. The warning
filter is not thread-safe; revisit before parallel scans.

## The directory skip list is conservative
The walker skips clear dependency and cache folders such as `.git`, `.venv`,
`__pycache__`, and `node_modules`. Hidden source folders such as `.github` stay
included. Ambiguous folders such as `build`, `dist`, and `env` are not skipped.
Revisit if a real scan shows this indexes too much; honoring `.gitignore` is a
possible next step.

## Python files use Python's source decoding rules
`read_source` uses `tokenize.open`, which honors a UTF-8 BOM and PEP 263 coding
comments. Plain UTF-8 decoding would reject some valid Python files.

## The chunker parses and slices one source string
`chunk_repo` reads each candidate Python file with `read_source`, then passes
that same decoded string to `make_chunks` for parsing and source slicing. This
avoids a second read and prevents the parser's ranges from referring to an
earlier file version. Each file is read and parsed once by `chunk_repo`.
`walk_repo` remains a separate metadata-only scan and is not in this path.

## Chunk types and overlap
- `function`: functions and methods at any nesting depth, starting at their
  first decorator.
- `class`: class decorators and header, plus the docstring when present.
- `module`: consecutive top-level statements other than direct function and
  class definitions.

Nested functions overlap their enclosing function chunks. A top-level compound
statement such as an `if` can contain a definition and be included in a module
chunk too. This simple rule preserves source context; search results may
overlap. Class-level attributes and comments between statements are not
separate chunks.

## Chunk line boundaries match Python's parser
`make_chunks` splits only on CRLF, CR, or LF with a regex. `str.splitlines()`
also treats form feed and U+2028 as line boundaries, which can shift source
ranges relative to Python's AST. Chunk text is joined with `\n`, retains source
indentation, and omits a trailing newline.

## Long chunks split by line count
Chunks longer than `max_lines` (default 150) are divided into consecutive
parts with exact inclusive line ranges. Parts do not overlap and can end in
the middle of a logical block. Revisit after retrieval results show whether
smarter split points would help.

## Chunk IDs are content-based
The ID hashes path, kind, qualified name, part number, and chunk text; line
numbers are excluded. Shifting unchanged code keeps its ID, while changing the
code changes it. Duplicate identical definitions receive a suffix to keep IDs
unique within one file. Database key and cross-repository deduplication rules
remain open for the storage phase.

## Search text separates source from location context
`Chunk.text` remains source code. `Chunk.search_text` prepends its path and
qualified name for future embedding input. Current keyword search tokenizes
the source and boosts path/name matches separately.

## Retrieval evaluation uses a separate sample repository
The bundled questions evaluate `tests/fixtures/sample_repo`, not this project's
own source. Each question has an `expected` list of acceptable `(path,
qualified_name)` pairs. The evaluator reports Recall@k and MRR@k; questions
whose expected chunks do not exist are marked `UNANSWERABLE` and excluded from
both metric denominators. A caller must provide the repository path, and
skipped files are printed as warnings.

The fixture is deliberately small and synthetic. Its results check the
evaluation flow, not general search quality. For stronger comparisons, add a
larger independent sample repository and keep its question set fixed.

## Initial storage models
SQLAlchemy models describe repositories, repository-relative files, and code
chunks. A chunk keeps its stable chunker ID, source text, and inclusive line
range so retrieval results can later be cited. Database rows use integer
primary keys; the chunker's ID remains a separate unique key within its file.
The in-memory SQLite test checks the model relationships quickly. It is not a
substitute for testing against PostgreSQL, which is still the intended runtime
database. Database connections, migrations, embeddings, and ingestion writes
are not implemented yet.
