import pytest
from main import extract_functions, extract_functions_from_source


def test_empty_and_functionless_sources():
    # [] must mean exactly "valid file, no functions"
    assert extract_functions_from_source("") == []
    assert extract_functions_from_source("x = 42\nimport os\n") == []


def test_top_level_and_control_blocks():
    # Functions hidden inside try/except and if blocks must still be found
    source = """try:
    import ujson as json
except ImportError:
    def json_fallback():
        pass

if __name__ == "__main__":
    def main():
        pass
"""
    expected = [
        {"name": "json_fallback", "qualified_name": "json_fallback", "start_line": 4, "end_line": 5},
        {"name": "main", "qualified_name": "main", "start_line": 8, "end_line": 9},
    ]
    assert extract_functions_from_source(source) == expected


def test_nested_classes_and_functions():
    # Qualified names must reflect nesting at any depth
    source = """def outer():
    def inner():
        pass

class A:
    class B:
        def deep(self):
            pass
"""
    expected = [
        {"name": "outer", "qualified_name": "outer", "start_line": 1, "end_line": 3},
        {"name": "inner", "qualified_name": "outer.inner", "start_line": 2, "end_line": 3},
        {"name": "deep", "qualified_name": "A.B.deep", "start_line": 7, "end_line": 8},
    ]
    assert extract_functions_from_source(source) == expected


def test_async_method_in_class():
    source = """class Client:
    async def fetch(self):
        return await something()
"""
    expected = [
        {"name": "fetch", "qualified_name": "Client.fetch", "start_line": 2, "end_line": 3},
    ]
    assert extract_functions_from_source(source) == expected


def test_decorated_function_starts_at_first_decorator():
    # Without the decorator_list fix, start_line would be 3, not 1
    source = """@login_required
@cache(timeout=60)
async def dashboard(request):
    return "ok"
"""
    expected = [
        {"name": "dashboard", "qualified_name": "dashboard", "start_line": 1, "end_line": 4},
    ]
    assert extract_functions_from_source(source) == expected


def test_parse_errors_raise():
    with pytest.raises(SyntaxError):
        extract_functions_from_source("def broken(x:\n    return x")

    # Null bytes raise ValueError on older Pythons and SyntaxError on newer
    # ones, so accept either instead of pinning one interpreter's behavior
    with pytest.raises((SyntaxError, ValueError)):
        extract_functions_from_source("def f(): pass\x00")


def test_extract_functions_reads_a_real_file(tmp_path):
    # Happy path: the file wrapper reads the file and passes the source along
    good_file = tmp_path / "good.py"
    good_file.write_text("def hello():\n    pass\n", encoding="utf-8")
    expected = [
        {"name": "hello", "qualified_name": "hello", "start_line": 1, "end_line": 2},
    ]
    assert extract_functions(good_file) == expected


def test_file_errors_raise(tmp_path):
    # These errors come from open(), not our logic. The test documents the
    # contract that they propagate, which the repo walker will rely on.
    with pytest.raises(FileNotFoundError):
        extract_functions(tmp_path / "does_not_exist.py")

    invalid_utf8_file = tmp_path / "invalid_utf8.py"
    invalid_utf8_file.write_bytes(b"# \xff\xfe invalid utf-8\ndef f(): pass\n")
    with pytest.raises(UnicodeDecodeError):
        extract_functions(invalid_utf8_file)