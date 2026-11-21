# Ask Your Repo: Architecture

A proposed design for a service that answers questions about a codebase and cites the exact file and line numbers behind every answer.

> This is a design to build toward, not a description of what exists today. The function extractor (Stage 2 below) is the only piece written so far.

---

## 1. What the system does

**Input:** a code repository and a question, e.g. *"Where do we validate user tokens?"*

**Output:** an answer plus citations, e.g. `auth/tokens.py:42-67 (verify_token)`.

**The key idea:** an LLM can't read a whole repo at once. So we split the system in two:

1. **Ingestion (offline, slow):** read the repo once and build a searchable index.
2. **Query (online, fast):** for each question, find the few relevant pieces of code and hand only those to the LLM.

This pattern is called **RAG** (Retrieval-Augmented Generation).

---

## 2. High-level picture

```
INGESTION (runs once per repo, and again when the repo changes)

 Repo ──► File walker ──► Parser/Extractor ──► Chunker ──► Embedder ──► Index
          (find .py)      (ast: functions,     (one chunk   (text →      (vector DB
                           lines, names)        per function) vector)      + metadata DB)


QUERY (runs on every question)

 Question ──► API ──► Embed question ──► Retrieve top-k chunks ──► Build prompt ──► LLM
                                              ▲                                      │
                                              │                                      ▼
                                           Index                          Answer + citations
                                                                                     │
                                                                          Validate citations
                                                                                     │
                                                                                     ▼
                                                                                  Response
```

---

## 3. Components

### Stage 1: File walker
Walks the repo and picks files worth indexing. It skips `node_modules`, `.git`, build output, binaries, and huge generated files. Respecting `.gitignore` is a good default.

### Stage 2: Parser / function extractor *(already built)*
Uses Python's `ast` module to find every function and method, returning:

| Field | Example |
|---|---|
| `name` | `verify_token` |
| `qualified_name` | `TokenService.verify_token` |
| `start_line` | `42` |
| `end_line` | `67` |

This is what makes **line-accurate citations** possible. Plain text splitting can't tell you where a function starts and ends.

### Stage 3: Chunker
Turns each extracted function into a **chunk**: the source text plus its metadata.

Design decisions to make here:
- **Granularity:** one chunk per function is a good start. Very large functions may need splitting; tiny ones may be grouped with their class.
- **Context:** prepend the file path and class name to the chunk text so the embedding captures *where* the code lives.
- **Non-function code:** module-level constants, imports, and docstrings matter too. Add a "module" chunk per file later.

### Stage 4: Embedder
Converts each chunk's text into a vector (a list of numbers) using an embedding model. Chunks with similar meaning end up with nearby vectors, which is what makes semantic search work.

### Stage 5: Index (storage)
Two kinds of data, two kinds of storage:

| Data | Stored in | Why |
|---|---|---|
| Vectors | Vector index (e.g. pgvector, Qdrant, FAISS) | Fast nearest-neighbor search |
| Chunk text + metadata | Relational DB (e.g. PostgreSQL) | Exact lookups, filtering, joins |

A simple starting point is **PostgreSQL with pgvector**, which keeps both in one database.

### Stage 6: Retriever
On each question:
1. Embed the question.
2. Find the top-k most similar chunks (k around 5 to 10).
3. *(Later improvement)* combine with keyword search (BM25) and **re-rank** the results. Code questions often include exact identifiers like `verify_token`, which keyword search handles better than embeddings.

### Stage 7: Prompt builder
Assembles what the LLM sees:

```
You answer questions about a codebase using ONLY the snippets below.
Cite every claim as [file:start-end]. If the snippets don't contain
the answer, say so.

[auth/tokens.py:42-67]
<code of verify_token>

[auth/middleware.py:10-30]
<code of require_auth>

Question: Where do we validate user tokens?
```

### Stage 8: LLM
Generates the answer from the retrieved snippets only.

### Stage 9: Citation validator
After the LLM responds, **check its citations against what was actually retrieved.** If it cites a file or line range that wasn't in the prompt, flag or remove it. This guards against hallucinated citations and is what makes the "with citations" promise trustworthy.

---

## 4. Data model

```
repos
  id, url, name, last_indexed_commit, indexed_at

files
  id, repo_id, path, language, content_hash

chunks
  id, file_id, name, qualified_name,
  start_line, end_line, source_text,
  embedding (vector)

queries   (optional, for logging and evaluation)
  id, repo_id, question, answer, cited_chunk_ids, created_at
```

`content_hash` lets re-indexing skip files that haven't changed.

---

## 5. API sketch

```
POST /repos                    body: {"url": "..."}        → starts ingestion, returns repo_id
GET  /repos/{id}/status                                    → "indexing" | "ready" | "failed"
POST /repos/{id}/ask           body: {"question": "..."}   → {"answer": "...", "citations": [...]}
```

Ingestion is slow, so `POST /repos` should return immediately and do the work in the background (see section 6).

---

## 6. Where system design ideas apply

| Concern | Decision |
|---|---|
| **Slow ingestion** | Run it as a background job on a queue with a worker, not inside the web request. |
| **Read-heavy queries** | Cache answers to repeated questions (keyed by repo, commit, and question). |
| **Repo changes** | Re-index incrementally: compare `content_hash` per file and re-embed only what changed. |
| **Embedding cost/latency** | Batch chunks into one embedding request instead of one call per chunk. |
| **LLM latency** | Stream the answer to the client as it generates. |
| **Statelessness** | Keep the API server stateless so you can run several copies behind a load balancer. |
| **Multiple users/repos** | Always filter retrieval by `repo_id` so one repo's code never leaks into another's answers. |

---

## 7. Failure modes to design for

- **Retrieval misses the right code.** The LLM then answers confidently from the wrong snippets. Mitigation: hybrid search, re-ranking, and an "I couldn't find this" answer when similarity scores are low.
- **Hallucinated citations.** Mitigation: the validator in Stage 9.
- **Stale index.** The repo changed but the index didn't. Mitigation: store `last_indexed_commit` and show it in answers.
- **Unparseable files.** Syntax errors will crash `ast`. Mitigation: catch the error, log it, and fall back to plain text chunking for that file.
- **Prompt too long.** Too many or too large chunks. Mitigation: cap the token budget and trim the lowest-ranked chunks.

---

## 8. Suggested build order

Each step is usable on its own and teaches one concept:

1. **Extractor** *(done)*: parse a file into functions with line ranges.
2. **Repo-wide extractor:** walk a whole directory, handle errors, skip junk.
3. **Chunk storage:** save chunks and metadata to SQLite, then PostgreSQL.
4. **Embeddings + search:** embed chunks, run similarity search from a script.
5. **Answer generation:** build the prompt, call the LLM, print the answer.
6. **Citation validator:** reject citations not present in the retrieved chunks.
7. **HTTP API:** wrap steps 2 to 6 in a small web service.
8. **Background ingestion:** move indexing onto a queue and worker.
9. **Caching and incremental re-indexing.**
10. **Evaluation:** a fixed set of questions with known correct answers, to measure whether changes actually improve results.

---

## 9. Testing strategy

- **Unit tests:** extractor, chunker, and citation validator (deterministic, so easy to test with pytest).
- **Retrieval tests:** for a sample repo, assert that known questions retrieve the known correct function in the top-k.
- **End-to-end evals:** a question set with expected citations. Track the score over time so you can tell whether a change helped.

---

## 10. Key trade-offs

| Choice | Option A | Option B |
|---|---|---|
| Chunk size | Function-level: precise citations | File-level: more context, vaguer citations |
| Storage | pgvector: one database, simple | Dedicated vector DB: faster at large scale |
| Search | Embeddings only: simple | Hybrid + re-rank: better results, more moving parts |
| Ingestion | On-demand: always fresh | Scheduled or webhook-driven: cheaper per query |

**Recommended starting point:** function-level chunks, PostgreSQL with pgvector, embeddings-only search, and a background worker for ingestion. Add hybrid search once you can measure a retrieval problem.