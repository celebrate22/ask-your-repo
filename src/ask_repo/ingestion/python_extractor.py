import ast
import pprint


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


def extract_functions_from_source(source, filename="<string>"):
    """Return all functions in `source`, in file order.

    Raises SyntaxError if the source can't be parsed. An empty list means
    "valid code with no functions", never "something went wrong". Deciding
    what to do about broken files is the caller's job.
    """
    tree = ast.parse(source, filename=filename)
    visitor = QualifiedFunctionVisitor()
    visitor.visit(tree)
    return visitor.results  # already in file order, no sorting needed


def extract_functions(file_path):
    """Read a UTF-8 file and extract its functions.

    File errors (missing file, bad encoding) are deliberately not caught.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        source = file.read()
    return extract_functions_from_source(source, filename=str(file_path))
