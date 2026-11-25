import pytest

from ask_repo.ingestion.python_extractor import (
    extract_functions,
    extract_functions_from_source,
)


def test_extract_functions_reports_decorated_async_and_nested_functions():
    source = (
        "@cache\n"
        "async def outer():\n"
        "    def inner():\n"
        "        return 1\n"
        "    return inner()\n"
    )

    assert extract_functions_from_source(source) == [
        {
            "name": "outer",
            "qualified_name": "outer",
            "start_line": 1,
            "end_line": 5,
        },
        {
            "name": "inner",
            "qualified_name": "outer.inner",
            "start_line": 3,
            "end_line": 4,
        },
    ]


def test_extract_functions_reports_class_method_qualified_name():
    source = "class Service:\n    def run(self):\n        return True\n"

    assert extract_functions_from_source(source) == [{
        "name": "run",
        "qualified_name": "Service.run",
        "start_line": 2,
        "end_line": 3,
    }]


def test_extract_functions_from_source_raises_for_invalid_python():
    with pytest.raises(SyntaxError):
        extract_functions_from_source("def broken(:\n    pass\n")


def test_extract_functions_reads_python_encoding_declarations(tmp_path):
    source_file = tmp_path / "latin.py"
    source_file.write_bytes(
        b"# -*- coding: latin-1 -*-\n"
        b"label = '\xe9'\n"
        b"def get_label():\n    return label\n"
    )

    assert extract_functions(source_file)[0]["qualified_name"] == "get_label"
