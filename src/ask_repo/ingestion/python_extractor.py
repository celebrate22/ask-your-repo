"""Extract function and method locations from Python source code."""

import ast
import tokenize
import warnings


class QualifiedFunctionVisitor(ast.NodeVisitor):
    """Walks a parsed Python file and records every function and method.

    `scope` is the trail of enclosing names (classes and functions) at the
    current position, which is how we get names like "A.B.deep".
    """

    def __init__(self):
        self.results = []
        self.scope = []

    def visit_ClassDef(self, node):
        # Classes aren't recorded themselves; they only add to the trail.
        self.scope.append(node.name)
        try:
            self.generic_visit(node)  # look at everything inside the class
        finally:
            self.scope.pop()  # always leave the trail clean, even on error

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        try:
            # A decorated function starts at its first decorator, not the
            # `def` line, so citations include the whole function.
            start_line = (
                node.decorator_list[0].lineno
                if node.decorator_list
                else node.lineno
            )
            self.results.append({
                "name": node.name,
                "qualified_name": ".".join(self.scope),
                "start_line": start_line,
                "end_line": node.end_lineno,  # needs Python 3.8+
            })
            self.generic_visit(node)  # functions can contain functions
        finally:
            self.scope.pop()

    def visit_AsyncFunctionDef(self, node):
        # Async functions are treated exactly like normal ones.
        self.visit_FunctionDef(node)


def parse_source(source, filename="<string>"):
    """Parse Python source into an AST, without printing the code's warnings.

    Scanned code can make Python print warnings (for example "invalid
    escape sequence"). Those are the scanned repo's problem, not ours, so
    keep them out of our output. Only the parse call is wrapped.
    Raises SyntaxError (and, for pathological input, RecursionError or
    MemoryError). Never swallows them: the caller decides what to do.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(source, filename=filename)


def read_source(file_path):
    """Read a Python source file the way Python itself does.

    tokenize.open honors a UTF-8 BOM and a PEP 263 coding comment such as
    "# -*- coding: latin-1 -*-". Plain open(..., encoding="utf-8") would
    make a BOM file fail to parse and a latin-1 file fail to decode, so a
    perfectly valid file would be reported as broken.
    Raises OSError (missing/unreadable file) and SyntaxError or
    UnicodeDecodeError (undecodable bytes).
    """
    with tokenize.open(file_path) as file:
        return file.read()


def extract_functions_from_source(source, filename="<string>"):
    """Return all functions in `source`, in file order.

    Raises SyntaxError if the source can't be parsed. An empty list means
    "valid code with no functions", never "something went wrong". Deciding
    what to do about broken files is the caller's job.
    """
    tree = parse_source(source, filename=filename)
    visitor = QualifiedFunctionVisitor()
    visitor.visit(tree)
    return visitor.results  # already in file order, no sorting needed


def extract_functions(file_path):
    """Read a Python file and extract its functions.

    File errors (missing file, undecodable bytes) are deliberately not caught.
    """
    return extract_functions_from_source(read_source(file_path), filename=str(file_path))