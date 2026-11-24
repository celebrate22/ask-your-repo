import pytest
from ask_repo.ingestion.walker import find_python_files


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_python_files(tmp_path / "missing")


def test_missing_folder_message_shows_resolved_path(tmp_path, monkeypatch):
    # A RELATIVE path is where the confusion happens: "python-course" means
    # "inside whatever folder you ran the command from". The message must
    # show the absolute path Python actually searched.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError) as excinfo:
        find_python_files("python-course")
    assert str(tmp_path.resolve() / "python-course") in str(excinfo.value)


def test_file_path_raises(tmp_path):
    single_file = tmp_path / "script.py"
    single_file.write_text("x = 1", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        find_python_files(single_file)


def test_empty_folder_returns_empty_list(tmp_path):
    assert find_python_files(tmp_path) == []


def _create(root, rel_paths):
    for rel in rel_paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# dummy", encoding="utf-8")


def test_hidden_folders_are_kept(tmp_path):
    # Hidden folders like .github hold real code; only known junk is skipped
    _create(tmp_path, [".github/workflows/ci.py", "main.py"])
    assert find_python_files(tmp_path) == [".github/workflows/ci.py", "main.py"]


def test_junk_folders_are_pruned_at_any_depth(tmp_path):
    _create(tmp_path, [
        "main.py",
        "pkg/mod.py",
        ".venv/lib/site.py",
        "pkg/venv/x.py",          # nested junk
        "__pycache__/main.cpython-312.py",
        ".pytest_cache/v/cache/stepwise.py",
        ".git/hooks/pre-commit.py",
        "node_modules/some_pkg/index.py",
    ])
    assert find_python_files(tmp_path) == ["main.py", "pkg/mod.py"]


def test_only_python_files_are_listed(tmp_path):
    _create(tmp_path, ["a.py", "README.md", "notes.txt", "data.json"])
    assert find_python_files(tmp_path) == ["a.py"]


def test_broken_python_files_are_still_listed(tmp_path):
    # This function finds files; it never parses them. Parsing failures
    # are walk_repo's job.
    (tmp_path / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    assert find_python_files(tmp_path) == ["broken.py"]


def test_results_are_sorted_posix_relative_paths(tmp_path):
    _create(tmp_path, ["z.py", "pkg/b.py", "pkg/a.py", "a.py"])
    assert find_python_files(tmp_path) == ["a.py", "pkg/a.py", "pkg/b.py", "z.py"]