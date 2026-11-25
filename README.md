# ask-your-repo

A learning project for exploring Python repositories, finding relevant code,
and eventually answering questions with source citations.

## Current capabilities

The project currently supports local Python ingestion and keyword retrieval.
It does not yet call an LLM, create embeddings, or store chunks in a database.
It also exposes a small FastAPI health endpoint at `/health`.

`chunk_repo(root)` finds Python files, reads and parses each source once, and
returns a `ChunkScan` with `chunks` and `skipped` records. A frozen `Chunk`
includes a stable ID, repository-relative `path`, `kind`, qualified name,
source line range, source `text`, and part metadata. The `search_text` property
adds location context for future embedding. Current keyword search tokenizes
source text and boosts path/name matches separately.

Chunk kinds are:

- `function`: functions and methods, including nested functions.
- `class`: the class header and its docstring, if present.
- `module`: consecutive top-level statements that are not direct definitions.

Chunks longer than 150 lines are divided into consecutive parts by default.
Their ranges are inclusive. `text` is built from the same decoded source string
that the parser used, split only at CRLF, CR, or LF boundaries.

For example:

```python
from ask_repo.ingestion.chunker import chunk_repo

scan = chunk_repo(".")
for chunk in scan.chunks:
    print(f"{chunk.path}:{chunk.start_line}-{chunk.end_line} [{chunk.kind}]")
    print(chunk.text)
for skipped in scan.skipped:
    print(f"Skipped {skipped['file']}: {skipped['error_type']}")
```

`make_chunks(path, source, *, max_lines=150)` is the pure source-to-chunks
function. It parses the supplied source and can be tested without filesystem
access. `walk_repo(root)` remains a separate helper that reports function
metadata and skipped files; `chunk_repo` performs its own scan so parsing and
chunk slicing use the same source string.

Install the package and development dependency, then run the tests:

```sh
python -m pip install -e '.[dev]'
pytest
```

Run the API locally with Uvicorn:

```sh
uvicorn ask_repo.api.app:app --reload
```

Open `http://127.0.0.1:8000/health`; the response should be
`{"status":"ok"}`. The health endpoint confirms that the API process is
responding. It does not yet check a database or other services.

## Keyword retrieval evaluation

`keyword_search(chunks, query)` ranks chunks with BM25-style keyword matching
and gives extra weight to file and function names. It selects evidence; it does
not write answers.

The bundled questions use a small fixture repository, not this project's own
source. Run them from the project root:

```sh
PYTHONPATH=src python -m ask_repo.evals.run_eval tests/fixtures/sample_repo
```

Current fixture result: **Recall@5 100% and MRR@5 1.000** across six
answerable questions; one question is correctly marked unanswerable because
its expected function is absent. This synthetic set checks that the pipeline
runs; it is too small to measure general retrieval quality.
