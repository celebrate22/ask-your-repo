# Ask Your Repo: architecture and working rules

For humans and coding agents. Read this before changing anything.

## What it is
A service that takes a codebase and answers questions about it, citing the
exact files and lines. It is also a learning project: the owner is building it
to learn production AI engineering. Prefer explaining and reviewing over
writing everything for them, and never build ahead of what was asked.

## Architecture
```
                         ┌──────────────┐
   User ───────────────▶ │  API layer   │  FastAPI: accept repo URL, accept questions
                         └──────┬───────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
 ┌──────────────┐        ┌──────────────┐         ┌──────────────┐
 │  Ingestion   │        │  Answering   │         │  Evaluation  │
 │ [x] walker   │        │ retrieval    │         │ question set │
 │ [x] extractor│        │   or agent   │         │ scoring      │
 │ [x] chunker  │        │ build answer │         │ recall@k     │
 │ [ ] GitHub   │        │ cite sources │         │ cost/latency │
 └──────┬───────┘        └──────┬───────┘         └──────────────┘
        ▼                       ▼
 ┌──────────────────────────────────┐        ┌──────────────┐
 │  Storage: Postgres (+ pgvector)  │        │ LLM API +    │
 │  repos, files, chunks, embeddings│        │ embeddings   │
 └──────────────────────────────────┘        └──────────────┘

 Across everything: config, logging, tests, error handling, Docker/deploy
```
Open decision: indexed RAG, agentic search (grep / read_file tools), or both
compared head to head. Not decided yet. Do not pick one silently.

Ingestion flow (built):
```
folder -> find_python_files -> read_source -> make_chunks -> [Chunk]
            (walker)          (extractor)      (chunker: parses and
                                                slices the same string)
          \______________ chunk_repo ______________/
```
`walk_repo` (functions only, no text) remains as a separate scan.
A Chunk has: id, path, kind (function | class | module), name,
qualified_name, start_line, end_line, text, part, parts, plus a
`search_text` property for embedding.

## Layer rule
`api` calls `answering`, which calls `retrieval`, which calls `storage`.
Never the reverse. Routes contain no queries or prompts.

## Project structure (current status)
```
ask-your-repo/
├── pyproject.toml                  [x] package and test configuration
├── README.md                       [x] ingestion and evaluation usage
├── docs/decisions.md               [x] why each choice was made
├── src/ask_repo/
│   ├── ingestion/
│   │   ├── python_extractor.py     [x] functions + line ranges from source
│   │   ├── walker.py               [x] find files, skip junk, report skipped
│   │   ├── chunker.py              [x] source -> function/class/module chunks
│   ├── retrieval/
│   │   ├── __init__.py
│   │   └── search.py               [x] keyword search; embeddings not started
│   ├── storage/
│   │   └── models.py               [started] repositories, files, and chunks
│   ├── api/
│   │   ├── app.py                  [x] FastAPI app and route registration
│   │   └── routes/health.py        [x] `/health` endpoint
│   └── evals/
│       ├── __init__.py
│       ├── dataset/questions.jsonl [x] questions for sample_repo
│       ├── metrics.py              [x] Recall@k and MRR@k
│       └── run_eval.py             [x] evaluation command
└── tests/
    ├── fixtures/sample_repo/       [x] small independent eval corpus
    ├── test_python_extractor.py    [x]
    ├── test_find_python_files.py   [x]
    ├── test_walker.py              [x]
    ├── test_chunker.py             [x]
    ├── test_eval_metrics.py        [x]
    ├── integration/test_health.py [x]
    └── storage/test_models.py     [x]
```
`ask_repo`, `ingestion`, `storage`, and `api` rely on namespace-package
behavior; `retrieval` and `evals` have explicit `__init__.py` files. Storage
currently has model definitions only: database connections, migrations, and
writing ingested chunks remain to be built. Embeddings, answering, background
jobs, and deployment also remain unbuilt. No empty GitHub client placeholder
is needed.

## Working rules
1. **Test first.** Write the failing test, with expected values worked out by
   hand, and see it fail for the right reason before writing the code. Check
   that a new test can fail: run it against the old or a deliberately wrong
   version.
2. **No silent failures.** `[]` must mean exactly one thing. No bare
   `except Exception`. Keep every `try` as narrow as possible. Known file
   problems are listed explicitly (see `SKIPPABLE_ERRORS` in walker.py), so
   bugs in our own code still crash loudly.
3. **Lines are split with a regex**, not `str.splitlines()`. Python counts
   only `\n`, `\r\n`, `\r` as line breaks; `splitlines()` shifts line numbers
   on form feeds and U+2028. Chunk text is cut from the same string that was
   parsed. Python files are read with `read_source` (BOM and coding comments).
4. **Evidence, not claims.** Run `pytest` and report the real output. Never
   say something works without running it.
5. **Small steps.** One piece at a time, reviewed before the next.
6. **Write down decisions** in `docs/decisions.md`: what was chosen, why, what
   would change the mind.
7. Python 3.12, distribution name `askrepo`, import package `ask_repo`, and
   `src` layout. Install with `pip install -e '.[dev]'`; run tests with
   `pytest` from the project root.

## Current state and next step
Local Python ingestion, keyword search, and retrieval evaluation work. A
minimal FastAPI app exposes `/health`. Initial SQLAlchemy models describe
repositories, files, and chunks; they are checked with an in-memory SQLite
test, not PostgreSQL. Next: configure a database connection, then create
migrations and store chunks from ingestion. The RAG versus agent direction is
still open.
