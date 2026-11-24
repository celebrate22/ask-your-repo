# Decisions

Short notes on real choices: what I chose, why, and what would change my mind.

## Syntax errors raise instead of returning []
`extract_functions_from_source` raises on unparsable source. `[]` therefore
means exactly one thing: valid code with no functions. `walk_repo` decides
what to do about broken files (record and continue).
Revisit if: a caller needs partial results from broken files.

## Scan errors are an explicit list, not `except Exception`
`SKIPPABLE_ERRORS` = SyntaxError, ValueError (includes UnicodeDecodeError and
null bytes), OSError, RecursionError, MemoryError. The last two come from
pathological files: a very long expression chain overflows the parser with
RecursionError, a long run of unary operators with MemoryError ("Parser stack
overflowed"). A bare `except Exception` would report bugs in our own code as
"bad files". A test checks an unexpected error still crashes.
Caveat: MemoryError could in principle be a real out-of-memory condition; the
skipped entry keeps the message visible so it can be told apart.

## Warnings from scanned code are silenced during parsing only
Scanned code can make Python warn (for example invalid escape sequences). Only
the `ast.parse` call is wrapped in `warnings.catch_warnings()`.
Caveat: `catch_warnings` is not thread-safe. Revisit when scans run in threads
or an async API.

## Skip list is conservative
Only unambiguous tool, cache and dependency folders are skipped (.git, venv,
.venv, __pycache__, caches, .tox, node_modules). Hidden folders like .github
are kept. `env`, `build` and `dist` are NOT skipped, because they can be
real source folders.
Cost: a repo that contains a virtualenv named `env/` will be fully indexed,
library code included.
Revisit if: that hurts in a real scan. Likely fix: honor the repo's .gitignore.

## Missing folders fail loudly, with the resolved path
`find_python_files` raises FileNotFoundError / NotADirectoryError, and the
message shows the absolute path searched, because relative-path mistakes are
the most common cause.

## Known limits (not bugs)
- Only functions and methods are extracted. Module-level code, constants and
  class docstrings never become chunks.
- `A.method` and `outer.inner` are indistinguishable (no `kind` field yet).
- Python files only.