"""A module that uses a name must import it. py_compile cannot see this; a missing import only fails when the code runs."""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names |= {a.asname or a.name for a in node.names}
    return names


def test_modules_that_call_tracing_import_it():
    missing = []
    for path in list(APP.rglob("*.py")) + list(SCRIPTS.glob("*.py")):
        if path.name == "tracing.py":
            continue
        tree = ast.parse(path.read_text())
        uses = any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "tracing"
                   for n in ast.walk(tree))
        if uses and "tracing" not in _imported_names(tree):
            missing.append(str(path.relative_to(APP.parent)))
    assert not missing, f"use 'tracing' without importing it: {missing}"
