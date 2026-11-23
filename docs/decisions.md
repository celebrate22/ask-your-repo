# Architectural Decisions

This document records the core engineering decisions, trade-offs, and constraints for `ask-your-repo`.

---

## 1. Empty Results Must Have One Meaning (`[]` vs. Exceptions)

* **Decision:** Functions that scan directories or extract code elements must never silently swallow missing paths or invalid inputs by returning `[]`. Instead, invalid inputs raise explicit exceptions (`FileNotFoundError`, `NotADirectoryError`, etc.), leaving `[]` to mean strictly *"the input was valid, and zero items matched."*
* **Why:** If both a misspelled directory path and an empty repository return `[]`, bugs go undetected and callers cannot distinguish between "nothing here" and "broken path."
* **What would change our mind:** Nothing for core library functions. Higher-level CLI or UI layers may catch these exceptions to display user-friendly messages, but internal functions will always fail loudly.

---

## 2. Conservative v1 Directory Skip Policy (`walker.py`)

* **Decision:** Skip only unambiguous tool, cache, and dependency directories (`.git`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `node_modules`). Do **not** skip hidden folders (such as `.github/`) or potentially ambiguous folder names (`env/`, `build/`, `dist/`).
* **Why:** Silently dropping valid source code violates our principle that empty or missing results must be explicit. Folders named `build/` or `env/` can be legitimate application packages in real repositories, and `.github/` often contains automation scripts worth inspecting.
* **What would change our mind:** Seeing real-world repositories get polluted with third-party library code from a virtualenv named `env/`—at which point we will add `.gitignore` parsing so exclusions follow each repository's own rules.

---

## 3. POSIX Path Normalization (`walker.py`)

* **Decision:** Convert all returned relative file paths to POSIX format (`pkg/mod.py`) using `pathlib.Path(...).as_posix()`, regardless of the host operating system.
* **Why:** Citations, database keys, and test assertions should never depend on whether the tool ran on Linux, macOS, or Windows (`pkg\mod.py`).
* **What would change our mind:** Nothing. Internal path representations will remain POSIX-normalized across all versions.

---

## 4. Separate File Discovery from Parsing (`walker.py` vs. `python_extractor.py`)

* **Decision:** `find_python_files` discovers `.py` files purely by filename extension without reading or parsing their contents—meaning files with syntax errors (e.g., `broken.py`) are still returned in the file list.
* **Why:** Keeping discovery decoupled from AST parsing ensures `walk_repo` can account for every Python file in a repository and explicitly record which files failed to parse, rather than having broken files vanish silently during traversal.
* **What would change our mind:** Supporting extensionless Python scripts (e.g., CLI executables with `#!/usr/bin/env python3` shebangs), which would require inspecting file headers during discovry.
