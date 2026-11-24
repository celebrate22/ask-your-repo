# ask-your-repo
RAG-powered codebase explorer: ask questions about your repo and get line-by-line explanations and references.

## Ingestion flow

The current ingestion path turns Python functions in a repository into
citation-ready source chunks:

1. `find_python_files(root)` walks the directory tree and returns sorted,
   repository-relative `.py` paths. It skips common dependency and cache
   directories such as `.git`, `.venv`, and `node_modules`.
2. `walk_repo(root)` sends each file to the Python AST extractor. It gathers
   function and method names, qualified names, and inclusive line ranges. Known
   file and parser errors are recorded in `RepoScan.skipped`; other errors
   surface normally.
3. `chunk_repo(root)` reads each Python file once during chunk assembly and
   creates function chunks plus module chunks for consecutive top-level
   statements outside functions and classes. Each chunk includes its source in
   `text` and a file and line range for citations.

For example, from the repository root:

```python
from ask_repo.ingestion.chunker import chunk_repo

chunks = chunk_repo(".")
for chunk in chunks:
    print(f'{chunk["file"]}:{chunk["start_line"]}-{chunk["end_line"]}')
    print(chunk["text"])
```

This is the source preparation stage only: chunks are not embedded, persisted,
or searched yet. Module chunks can include imports, constants, and other
top-level statements. Class and function bodies are represented by their own
function chunks, not included in module chunks.

If the caller also needs to report files that could not be scanned, use
`chunk_repo_detailed(".")`. It returns an object with `chunks` and `skipped`
lists; `chunk_repo(".")` remains the concise option when only chunks are
needed.
