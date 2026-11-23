import pytest
from walker import find_python_files


def test_find_python_files_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_python_files(tmp_path / "missing")


def test_find_python_files_file_path_raises(tmp_path):
    single_file = tmp_path / "script.py"
    single_file.write_text("x = 1", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        find_python_files(single_file)


def test_find_python_files_empty_folder(tmp_path):
    assert find_python_files(tmp_path) == []


def test_find_python_files_keeps_hidden_folders(tmp_path):
    expected = [
        ".github/workflows/ci.py",
        "main.py",
    ]

    for rel_file in ["main.py", ".github/workflows/ci.py"]:
        file_path = tmp_path / rel_file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# dummy", encoding="utf-8")

    assert find_python_files(tmp_path) == expected


def test_find_python_files_prunes_root_and_nested_junk(tmp_path):
    expected = [
        "main.py",
        "pkg/mod.py",
    ]

    files_to_create = [
        "main.py",
        "README.md",
        "pkg/mod.py",
        ".venv/lib/site.py",
        "pkg/venv/x.py",
        "__pycache__/main.cpython-312.py",
        ".pytest_cache/v/cache/stepwise.py",
        ".git/hooks/pre-commit.py",
        "node_modules/some_pkg/index.py",
    ]

    for rel_file in files_to_create:
        file_path = tmp_path / rel_file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# dummy", encoding="utf-8")

    assert find_python_files(tmp_path) == expected


def test_find_python_files_includes_syntax_error_files(tmp_path):
    expected = ["broken.py", "valid.py"]

    (tmp_path / "valid.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    assert find_python_files(tmp_path) == expected
