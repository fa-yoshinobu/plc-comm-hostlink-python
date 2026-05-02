"""Validate user-facing high-level documentation coverage."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS_PATH = ROOT / "src" / "hostlink" / "utils.py"
INIT_PATH = ROOT / "src" / "hostlink" / "__init__.py"

REQUIRED_FUNCTIONS = {
    "parse_address": ("Args:", "Returns:", "Examples:"),
    "try_parse_address": ("Args:", "Returns:"),
    "format_address": ("Args:", "Returns:"),
    "read_typed": ("Args:", "Returns:", "Examples:"),
    "write_typed": ("Args:", "Examples:"),
    "write_bit_in_word": ("Args:", "Examples:"),
    "read_named": ("Args:", "Returns:", "Examples:"),
    "poll": ("Args:", "Yields:", "Usage::"),
    "read_expansion_unit_buffer": ("Args:", "Returns:", "Examples:"),
    "write_expansion_unit_buffer": ("Args:", "Examples:"),
    "read_words": ("Args:", "Returns:"),
    "read_dwords": ("Args:", "Returns:"),
    "open_and_connect": ("Args:", "Returns:", "Usage::"),
}


def _load_ast(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def main() -> int:
    errors: list[str] = []

    utils_module = _load_ast(UTILS_PATH)
    init_module = _load_ast(INIT_PATH)

    init_docstring = ast.get_docstring(init_module) or ""
    for helper_name in REQUIRED_FUNCTIONS:
        if helper_name not in init_docstring:
            errors.append(f"{INIT_PATH.name}: package docstring does not mention '{helper_name}'.")

    functions = {
        node.name: node for node in utils_module.body if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }

    for function_name, required_markers in REQUIRED_FUNCTIONS.items():
        node = functions.get(function_name)
        if node is None:
            errors.append(f"{UTILS_PATH.name}: missing helper function '{function_name}'.")
            continue

        docstring = ast.get_docstring(node) or ""
        if not docstring.strip():
            errors.append(f"{UTILS_PATH.name}: '{function_name}' is missing a docstring.")
            continue

        for marker in required_markers:
            if marker not in docstring:
                errors.append(f"{UTILS_PATH.name}: '{function_name}' docstring is missing required marker '{marker}'.")

    if errors:
        print("[ERROR] High-level docs coverage check failed.", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("[OK] High-level docs coverage check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
