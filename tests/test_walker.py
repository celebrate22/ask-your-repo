import pytest
from src.ask_repo.ingestion.walker import RepoScan, find_python_files, walk_repo


def make_fake_repo(tmp_path):
    """Create a realistic fake repo with valid files, broken files, and junk."""
    files = {
        "main.py": "def run():\n    return 1\n",
        "pkg/mod.py": "def helper(x):\n    return x + 1\n",
        ".github/workflows/ci.py": "def check():\n    pass\n",
        "broken_syntax.py": "def oops(:\n    pass\n",
        # Junk that must be ignored completely (not even in skipped)
        ".venv/lib/site.py": "def ignored():\n    pass\n",
        "__pycache__/cached.py": "def cached():\n    pass\n",
    }
    for rel_path, content in files.items():
        full_path = tmp_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    # Add a binary/invalid-UTF-8 .py file to trigger UnicodeDecodeError (a ValueError subclass)
    bad_bytes = tmp_path / "bad_encoding.py"
    bad_bytes.write_bytes(b"def f():\n    return '\xff\xfe'\n")

    return tmp_path


def test_walk_repo_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        walk_repo(tmp_path / "does_not_exist")


def test_walk_repo_extracts_functions_and_records_skipped(tmp_path):
    repo = make_fake_repo(tmp_path)

    result = walk_repo(repo)

    assert isinstance(result, RepoScan)

    # 1. Check extracted functions (each has its relative POSIX 'file' path attached)
    extracted_names_and_files = [(fn["file"], fn["name"]) for fn in result.functions]
    assert extracted_names_and_files == [
        (".github/workflows/ci.py", "check"),
        ("main.py", "run"),
        ("pkg/mod.py", "helper"),
    ]

    # 2. Check skipped files (bad_encoding.py and broken_syntax.py)
    skipped_files = [entry["file"] for entry in result.skipped]
    assert skipped_files == ["bad_encoding.py", "broken_syntax.py"]
    assert all("error" in entry and entry["error"] for entry in result.skipped)
