import ast
from pathlib import Path

from ask_repo.ingestion.chunker import chunk_repo, chunk_repo_detailed


def test_chunk_repo_returns_source_and_citation_metadata(tmp_path):
    source = (
        '"""Module docs."""\n'
        "from helpers import decorate\n"
        "@decorate\n"
        "def outer():\n"
        "    def inner():\n"
        "        return 'café'\n"
        "    return inner()\n"
    )
    (tmp_path / "example.py").write_text(source, encoding="utf-8")

    chunks = chunk_repo(tmp_path)

    function_chunks = [chunk for chunk in chunks if chunk["kind"] == "function"]
    assert [(chunk["name"], chunk["qualified_name"]) for chunk in function_chunks] == [
        ("outer", "outer"),
        ("inner", "outer.inner"),
    ]
    assert function_chunks[0] == {
        "file": "example.py",
        "name": "outer",
        "qualified_name": "outer",
        "kind": "function",
        "start_line": 3,
        "end_line": 7,
        "text": "@decorate\ndef outer():\n    def inner():\n        return 'café'\n    return inner()",
    }
    assert function_chunks[1]["text"] == "    def inner():\n        return 'café'"
    assert chunks[0] == {
        "file": "example.py",
        "name": "<module>",
        "qualified_name": "<module>",
        "kind": "module",
        "start_line": 1,
        "end_line": 2,
        "text": '"""Module docs."""\nfrom helpers import decorate',
    }


def test_chunk_repo_reads_each_file_once_even_with_multiple_functions(tmp_path, monkeypatch):
    source_file = tmp_path / "many.py"
    source_file.write_text("def first():\n    pass\n\ndef second():\n    pass\n", encoding="utf-8")
    read_paths = []
    original_read_text = Path.read_text

    def tracked_read_text(path, *args, **kwargs):
        read_paths.append(path)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked_read_text)

    chunks = chunk_repo(tmp_path)

    assert len(chunks) == 2
    assert read_paths == [source_file]


def test_chunk_repo_parses_each_file_once_for_both_chunk_types(tmp_path, monkeypatch):
    (tmp_path / "combined.py").write_text(
        "VALUE = 1\n\ndef first():\n    return VALUE\n\ndef second():\n    return first()\n",
        encoding="utf-8",
    )
    parse_count = 0
    original_parse = ast.parse

    def counted_parse(*args, **kwargs):
        nonlocal parse_count
        parse_count += 1
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(ast, "parse", counted_parse)

    chunks = chunk_repo(tmp_path)

    assert len(chunks) == 3
    assert parse_count == 1


def test_detailed_chunking_preserves_skipped_file_diagnostics(tmp_path):
    (tmp_path / "good.py").write_text("def ok():\n    return 42\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = chunk_repo_detailed(tmp_path)

    assert [chunk["name"] for chunk in result.chunks] == ["ok"]
    assert [(entry["file"], entry["error_type"]) for entry in result.skipped] == [
        ("broken.py", "SyntaxError"),
    ]


def test_chunk_repo_empty_repository_returns_no_chunks(tmp_path):
    assert chunk_repo(tmp_path) == []


def test_module_chunk_does_not_include_function_or_class_bodies(tmp_path):
    (tmp_path / "mod.py").write_text(
        "VALUE = 7\n\n"
        "def run():\n    return VALUE\n\n"
        "OTHER = 8\n\n"
        "class Service:\n    pass\n",
        encoding="utf-8",
    )

    chunks = chunk_repo(tmp_path)
    module_chunks = [chunk for chunk in chunks if chunk["kind"] == "module"]

    assert [
        (chunk["start_line"], chunk["end_line"], chunk["text"])
        for chunk in module_chunks
    ] == [
        (1, 1, "VALUE = 7"),
        (6, 6, "OTHER = 8"),
    ]
