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
3. `chunk_repo(root)` groups those functions by file, reads each relevant file
   once, and slices out the source lines for each function. Each returned chunk
   contains the function metadata plus its source in `text`.

For example, from the repository root:

```python
from ask_repo.ingestion.chunker import chunk_repo

chunks = chunk_repo(".")
for chunk in chunks:
    print(f'{chunk["file"]}:{chunk["start_line"]}-{chunk["end_line"]}')
    print(chunk["text"])
```

This is the source preparation stage only: chunks are not embedded, persisted,
or searched yet. Currently, ingestion extracts Python functions and methods;
module-level code and constants are not included.
