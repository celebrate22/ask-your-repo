import dataclasses

import pytest
from ask_repo.ingestion.chunker import Chunk, ChunkScan, chunk_repo, make_chunks

AUTH = """import os

def get_secret():
    return os.environ["SECRET"]

@cache
def verify_token(token):
    secret = get_secret()
    return token == secret
"""


def view(chunks):
    """(kind, qualified_name, start_line, end_line) for each chunk."""
    return [(c.kind, c.qualified_name, c.start_line, c.end_line) for c in chunks]


def by_name(chunks, qualified_name):
    return next(c for c in chunks if c.qualified_name == qualified_name)


# ---------- the three kinds of chunk ----------

def test_module_and_function_chunks_with_exact_text():
    chunks = make_chunks("app/auth.py", AUTH)

    assert view(chunks) == [
        ("module", "<module>", 1, 1),
        ("function", "get_secret", 3, 4),
        ("function", "verify_token", 6, 9),
    ]
    assert chunks[0].text == "import os"
    assert chunks[1].text == 'def get_secret():\n    return os.environ["SECRET"]'
    # The decorator line is part of the text, matching start_line=6
    assert chunks[2].text == "@cache\ndef verify_token(token):\n    secret = get_secret()\n    return token == secret"


def test_class_chunk_is_header_plus_docstring():
    source = 'class A:\n    """Docs."""\n    x = 1\n\n    def m(self):\n        return 1\n'
    chunks = make_chunks("a.py", source)
    assert view(chunks) == [("class", "A", 1, 2), ("function", "A.m", 5, 6)]
    assert chunks[0].text == 'class A:\n    """Docs."""'


def test_class_without_docstring_is_just_its_header():
    chunks = make_chunks("a.py", "class B(Base):\n    def m(self):\n        pass\n")
    assert view(chunks) == [("class", "B", 1, 1), ("function", "B.m", 2, 3)]
    assert chunks[0].text == "class B(Base):"


def test_one_line_class():
    (chunk,) = make_chunks("a.py", "class C: pass\n")
    assert (chunk.kind, chunk.start_line, chunk.end_line, chunk.text) == ("class", 1, 1, "class C: pass")


def test_multi_line_class_header():
    source = "class D(\n    Base,\n):\n    def m(self):\n        pass\n"
    chunks = make_chunks("a.py", source)
    assert view(chunks) == [("class", "D", 1, 3), ("function", "D.m", 4, 5)]
    assert chunks[0].text == "class D(\n    Base,\n):"


def test_decorated_class_starts_at_its_decorator():
    chunks = make_chunks("a.py", "@dataclass\nclass E:\n    x: int\n")
    assert view(chunks) == [("class", "E", 1, 2)]
    assert chunks[0].text == "@dataclass\nclass E:"


def test_consecutive_top_level_statements_form_one_module_chunk():
    source = (
        "import os\nimport sys\n\n"        # lines 1-3
        "def f():\n    pass\n\n"           # lines 4-6
        "X = 1\nY = 2\n\n"                 # lines 7-9
        'if __name__ == "__main__":\n    f()\n'  # lines 10-11
    )
    chunks = make_chunks("a.py", source)
    assert view(chunks) == [
        ("module", "<module>", 1, 2),
        ("function", "f", 4, 5),
        ("module", "<module>", 7, 11),
    ]
    assert chunks[2].text == 'X = 1\nY = 2\n\nif __name__ == "__main__":\n    f()'


def test_module_docstring_is_a_module_chunk():
    (chunk,) = make_chunks("a.py", '"""Docs."""\n')
    assert (chunk.kind, chunk.text) == ("module", '"""Docs."""')


def test_empty_and_comment_only_sources_have_no_chunks():
    assert make_chunks("a.py", "") == []
    assert make_chunks("a.py", "# just a comment\n\n") == []


# ---------- overlap rules ----------

def test_nested_functions_get_their_own_chunks_and_text_overlaps():
    # v1 rule: keep both. outer's text already contains inner's.
    chunks = make_chunks("a.py", "def outer():\n    def inner():\n        pass\n")
    assert view(chunks) == [("function", "outer", 1, 3), ("function", "outer.inner", 2, 3)]
    assert chunks[1].text in chunks[0].text


def test_function_inside_a_top_level_block_overlaps_the_module_chunk():
    # v1 rule: a top-level `if` is module code even when it contains a def,
    # so its function appears in both chunks.
    chunks = make_chunks("a.py", "if True:\n    def f():\n        pass\n")
    assert view(chunks) == [("module", "<module>", 1, 3), ("function", "f", 2, 3)]
    assert chunks[1].text in chunks[0].text


# ---------- exact text: line endings and odd characters ----------

def test_crlf_line_endings_give_clean_text():
    chunks = make_chunks("a.py", "def a():\r\n    pass\r\n\r\ndef b():\r\n    pass\r\n")
    assert by_name(chunks, "b").text == "def b():\n    pass"


@pytest.mark.parametrize(
    "source",
    [
        "def a():\n    pass\n\x0c\ndef b():\n    pass\n",   # form feed on its own line
        'x = "a\u2028b"\n\ndef b():\n    pass\n',          # U+2028 inside a string
    ],
)
def test_line_numbers_match_pythons_own_counting(source):
    # str.splitlines() would split on these characters and cut the wrong text
    assert by_name(make_chunks("a.py", source), "b").text == "def b():\n    pass"


# ---------- splitting long chunks ----------

LONG = "def f():\n" + "".join(f"    v{i} = {i}\n" for i in range(9))  # 10 lines


def test_long_chunks_are_split_into_parts_with_exact_ranges():
    chunks = make_chunks("a.py", LONG, max_lines=4)
    assert [(c.start_line, c.end_line, c.part, c.parts) for c in chunks] == [
        (1, 4, 1, 3), (5, 8, 2, 3), (9, 10, 3, 3),
    ]
    assert {c.qualified_name for c in chunks} == {"f"}
    assert "\n".join(c.text for c in chunks) == LONG.rstrip("\n")
    assert len({c.id for c in chunks}) == 3


def test_short_chunks_are_not_split():
    (chunk,) = make_chunks("a.py", LONG, max_lines=10)
    assert (chunk.part, chunk.parts, chunk.end_line) == (1, 1, 10)


def test_max_lines_must_be_positive():
    with pytest.raises(ValueError):
        make_chunks("a.py", LONG, max_lines=0)


# ---------- ids ----------

def test_id_survives_code_shifting_but_not_code_changing():
    plain = by_name(make_chunks("a.py", "def f():\n    return 1\n"), "f")
    shifted = by_name(make_chunks("a.py", "import os\n\n\ndef f():\n    return 1\n"), "f")
    changed = by_name(make_chunks("a.py", "def f():\n    return 2\n"), "f")

    assert plain.start_line != shifted.start_line   # the lines moved...
    assert plain.id == shifted.id                   # ...the id did not
    assert plain.id != changed.id                   # different code, different id


def test_same_code_in_different_files_has_different_ids():
    one = make_chunks("a.py", "def f():\n    return 1\n")[0]
    two = make_chunks("b.py", "def f():\n    return 1\n")[0]
    assert one.id != two.id


def test_identical_duplicate_definitions_still_get_unique_ids():
    source = "if X:\n    def f():\n        return 1\nelse:\n    def f():\n        return 1\n"
    functions = [c for c in make_chunks("a.py", source) if c.kind == "function"]
    assert len(functions) == 2
    assert functions[0].text == functions[1].text
    assert len({c.id for c in functions}) == 2


# ---------- chunk object ----------

def test_search_text_adds_location_but_text_stays_pure_source():
    chunk = by_name(make_chunks("app/auth.py", AUTH), "verify_token")
    assert chunk.search_text.startswith("app/auth.py :: verify_token\n@cache\n")
    assert chunk.text.startswith("@cache\n")


def test_chunks_are_frozen():
    chunk = make_chunks("a.py", "def f(): pass\n")[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.text = "changed"


# ---------- errors in make_chunks ----------

def test_syntax_error_raises():
    with pytest.raises(SyntaxError):
        make_chunks("a.py", "def oops(:\n")


# ---------- chunk_repo ----------

def write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.write_bytes if isinstance(content, bytes) else path.write_text)(content)


def make_fake_repo(root):
    write(root, "main.py", "def run():\n    return 1\n")
    write(root, "pkg/mod.py", "class A:\n    def m(self):\n        pass\n")
    write(root, "venv/lib.py", "def ignored():\n    pass\n")
    write(root, "broken.py", "def oops(:\n")
    write(root, "bom.py", b"\xef\xbb\xbfdef f():\n    pass\n")
    write(root, "latin.py", b"# -*- coding: latin-1 -*-\nx = '\xe9'\n\ndef g():\n    pass\n")
    write(root, "bad_bytes.py", b"def h():\n    pass\n\nx = '\xff\xfe'\n")
    write(root, "chain.py", "x = " + "+".join(["1"] * 100_000) + "\n")
    return root


def test_chunk_repo_chunks_every_readable_file_and_reports_the_rest(tmp_path):
    result = chunk_repo(make_fake_repo(tmp_path))

    assert isinstance(result, ChunkScan)
    assert [(c.path, c.kind, c.qualified_name) for c in result.chunks] == [
        ("bom.py", "function", "f"),            # BOM file is valid, not "broken"
        ("latin.py", "module", "<module>"),
        ("latin.py", "function", "g"),
        ("main.py", "function", "run"),
        ("pkg/mod.py", "class", "A"),
        ("pkg/mod.py", "function", "A.m"),
    ]
    assert by_name([c for c in result.chunks if c.path == "latin.py"], "<module>").text == "x = '\u00e9'"
    assert [(s["file"], s["error_type"]) for s in result.skipped] == [
        ("bad_bytes.py", "UnicodeDecodeError"),
        ("broken.py", "SyntaxError"),
        ("chain.py", "RecursionError"),
    ]
    assert all(s["message"] for s in result.skipped)


def test_chunk_repo_empty_folder(tmp_path):
    assert chunk_repo(tmp_path) == ChunkScan()


def test_chunk_repo_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        chunk_repo(tmp_path / "missing")


def test_chunk_repo_passes_max_lines_through(tmp_path):
    write(tmp_path, "a.py", LONG)
    assert len(chunk_repo(tmp_path, max_lines=4).chunks) == 3


def test_chunk_repo_does_not_hide_bugs_in_our_own_code(tmp_path, monkeypatch):
    write(tmp_path, "a.py", "def f():\n    pass\n")

    def buggy(path, source, **kwargs):
        raise KeyError("a bug in our own code")

    monkeypatch.setattr("ask_repo.ingestion.chunker.make_chunks", buggy)
    with pytest.raises(KeyError):
        chunk_repo(tmp_path)