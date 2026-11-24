import pytest
from ask_repo.ingestion.walker import RepoScan, find_python_files, walk_repo


def make_fake_repo(tmp_path):
    """Create a realistic fake repo with valid files, broken files, and junk."""
    files = {
        "main.py": "def run():\n    return 1\n",
        "pkg/mod.py": "def helper(x):\n    return x + 1\n",
        ".github/workflows/ci.py": "def check():\n    pass\n",
        "broken_syntax.py": "def oops(:\n    pass\n",
        ".venv/lib/site.py": "def ignored():\n    pass\n",
        "__pycache__/cached.py": "def cached():\n    pass\n",
    }
    for rel_path, content in files.items():
        full_path = tmp_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    bad_bytes = tmp_path / "bad_encoding.py"
    bad_bytes.write_bytes(b"def f():\n    return '\xff\xfe'\n")

    return tmp_path


def test_walk_repo_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        walk_repo(tmp_path / "does_not_exist")


def test_walk_repo_empty_folder_returns_empty_scan(tmp_path):
    assert walk_repo(tmp_path) == RepoScan()


def test_walk_repo_extracts_functions_with_file_paths(tmp_path):
    repo = make_fake_repo(tmp_path)
    result = walk_repo(repo)

    assert [(fn["file"], fn["name"]) for fn in result.functions] == [
        (".github/workflows/ci.py", "check"),
        ("main.py", "run"),
        ("pkg/mod.py", "helper"),
    ]

    # Verify one complete merged function dict to ensure **fn didn't drop or corrupt fields
    main_fn = next(fn for fn in result.functions if fn["file"] == "main.py")
    assert main_fn == {
        "file": "main.py",
        "name": "run",
        "qualified_name": "run",
        "start_line": 1,
        "end_line": 2,
    }


def test_walk_repo_records_skipped_files_by_error_type(tmp_path):
    repo = make_fake_repo(tmp_path)
    result = walk_repo(repo)

    assert [(entry["file"], entry["error_type"]) for entry in result.skipped] == [
        ("bad_encoding.py", "UnicodeDecodeError"),
        ("broken_syntax.py", "SyntaxError"),
    ]
    assert all(isinstance(entry["message"], str) and entry["message"] for entry in result.skipped)
