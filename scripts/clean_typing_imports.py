#!/usr/bin/env python3
"""Remove unused old-style typing imports from files with __future__ annotations.

With `from __future__ import annotations`, annotations become strings and don't
need runtime imports. Old generic types (Dict, List, Optional, etc.) can be
replaced with builtins (dict, list, X | None). This script removes old typing
symbols that are imported but not actually used in code or annotation strings.

Uses AST-based analysis to distinguish real usage (code + annotations) from
incidental mentions in docstrings/comments.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

# Old typing symbols that have builtin/PEP 604 replacements
OLD_TYPING_SYMBOLS = {
    "Dict", "List", "Optional", "Tuple", "Set", "FrozenSet",
    "Type", "Union", "Deque", "DefaultDict", "Sequence",
}


def _collect_annotation_strings(tree: ast.AST) -> list[str]:
    """Extract all type-annotation string values from the AST.

    With ``from __future__ import annotations``, annotations are stored as
    ``ast.Constant`` string nodes rather than resolved ``ast.Name`` nodes.
    """
    annotations: list[str] = []
    for node in ast.walk(tree):
        # Function / method return type
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns and isinstance(node.returns, ast.Constant) and isinstance(node.returns.value, str):
                annotations.append(node.returns.value)
        # Parameter annotations
        if isinstance(node, ast.arg):
            if node.annotation and isinstance(node.annotation, ast.Constant) and isinstance(node.annotation.value, str):
                annotations.append(node.annotation.value)
        # Variable annotations  (x: int = ...)
        if isinstance(node, ast.AnnAssign):
            if node.annotation and isinstance(node.annotation, ast.Constant) and isinstance(node.annotation.value, str):
                annotations.append(node.annotation.value)
    return annotations


def _symbol_in_annotations(symbol: str, annotations: list[str]) -> bool:
    """Return True if *symbol* appears as a word in any annotation string."""
    pat = re.compile(r"(?<![A-Za-z_0-9])" + re.escape(symbol) + r"(?![A-Za-z_0-9])")
    return any(pat.search(a) for a in annotations)


def _symbol_in_code(tree: ast.AST, symbol: str, import_lineno: int) -> bool:
    """Return True if *symbol* appears as an ``ast.Name`` node outside the import."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol:
            if node.lineno != import_lineno:
                return True
        # typing.List style
        if isinstance(node, ast.Attribute) and node.attr == symbol:
            return True
    return False


def _find_typing_import_node(tree: ast.AST) -> ast.ImportFrom | None:
    """Find the first ``from typing import ...`` statement."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            return node
    return None


def _rebuild_import_line(orig_line: str, keep_names: list[str]) -> str | None:
    """Rebuild a ``from typing import ...`` line keeping only *keep_names*.

    Returns ``None`` if no names remain (the import should be deleted).
    Preserves the original formatting style (single-line vs multi-line).
    """
    if not keep_names:
        return None

    # Detect if the original is multi-line (parenthesised)
    if "(" in orig_line and ")" in orig_line:
        # Reconstruct as single-line parenthesised
        joined = ", ".join(keep_names)
        return f"from typing import ({joined})"
    # Single-line
    joined = ", ".join(keep_names)
    return f"from typing import {joined}"


def process_file(filepath: str, *, dry_run: bool = False) -> tuple[bool, list[str]]:
    """Process one file.  Returns (modified, log_messages)."""
    with open(filepath, "r", encoding="utf-8") as fh:
        content = fh.read()

    if "from __future__ import annotations" not in content:
        return False, []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False, [f"  SKIP (syntax error): {filepath}"]

    import_node = _find_typing_import_node(tree)
    if import_node is None:
        return False, []

    # Identify which imported names are old-style and unused
    annotations = _collect_annotation_strings(tree)
    removable: list[str] = []
    for alias in import_node.names:
        name = alias.name
        if name not in OLD_TYPING_SYMBOLS:
            continue
        in_code = _symbol_in_code(tree, name, import_node.lineno)
        in_ann = _symbol_in_annotations(name, annotations)
        if not in_code and not in_ann:
            removable.append(name)

    if not removable:
        return False, []

    # Build list of names to keep
    keep = [alias.name for alias in import_node.names if alias.name not in removable]
    log = [f"  {filepath}: remove {', '.join(removable)}"]

    if dry_run:
        return False, log

    # ---- Apply the edit ----
    lines = content.splitlines(keepends=True)

    # Find the original import text span (may be multi-line with parens / backslash)
    start_idx = import_node.lineno - 1  # 0-based
    end_idx = import_node.end_lineno - 1 if import_node.end_lineno else start_idx

    # Get the original text block
    orig_block = "".join(lines[start_idx : end_idx + 1])

    if keep:
        new_line = _rebuild_import_line(orig_block, keep) + "\n"
    else:
        new_line = ""  # delete entire import

    new_lines = lines[:start_idx] + ([new_line] if new_line else []) + lines[end_idx + 1 :]
    new_content = "".join(new_lines)

    # Verify the new content parses
    try:
        ast.parse(new_content)
    except SyntaxError as exc:
        return False, [f"  SKIP (edit would cause syntax error): {filepath}: {exc}"]

    with open(filepath, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_content)

    return True, log


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    project_root = Path(__file__).resolve().parent.parent

    skip_dirs = {"__pycache__", ".git", "node_modules", ".tox", "venv", ".venv"}
    skip_files = {"spiderfoot_pb2_grpc.py", "spiderfoot_pb2.py"}

    total = 0
    modified = 0
    all_log: list[str] = []

    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if not fname.endswith(".py") or fname in skip_files:
                continue
            total += 1
            path = os.path.join(root, fname)
            changed, log = process_file(path, dry_run=dry_run)
            if changed:
                modified += 1
            all_log.extend(log)

    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n[{mode}] Scanned {total} files, {modified} modified, {len(all_log)} with removable symbols:")
    for msg in all_log:
        print(msg)


if __name__ == "__main__":
    main()
