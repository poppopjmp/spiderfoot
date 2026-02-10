#!/usr/bin/env python3
"""Add from __future__ import annotations to all files with type annotations."""
import ast
import os


SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".tox"}
SKIP_FILES = {"spiderfoot_pb2_grpc.py", "spiderfoot_pb2.py"}
FUTURE_IMPORT = "from __future__ import annotations"


def has_type_annotations(tree: ast.AST) -> bool:
    """Check if AST has any type annotations."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns:
                return True
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                if arg.annotation:
                    return True
        if isinstance(node, ast.AnnAssign):
            return True
    return False


def find_insert_position(lines: list[str]) -> int:
    """Find the line index after initial comments/docstrings/encoding."""
    insert_idx = 0
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            insert_idx = i + 1
            i += 1
        elif stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 3:
                # Single-line docstring
                insert_idx = i + 1
                i += 1
            else:
                # Multi-line docstring
                j = i + 1
                while j < len(lines):
                    if quote in lines[j]:
                        insert_idx = j + 1
                        break
                    j += 1
                i = j + 1
        else:
            break
    return insert_idx


def main() -> None:
    modified = 0
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py") or f in SKIP_FILES:
                continue
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()

            if FUTURE_IMPORT in content:
                continue
            if not content.strip():
                continue

            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            if not has_type_annotations(tree):
                continue

            lines = content.split("\n")
            insert_idx = find_insert_position(lines)

            lines.insert(insert_idx, FUTURE_IMPORT)
            if insert_idx < len(lines) - 1 and lines[insert_idx + 1].strip():
                lines.insert(insert_idx + 1, "")

            new_content = "\n".join(lines)

            try:
                ast.parse(new_content)
            except SyntaxError as exc:
                print(f"SKIP {path}: {exc}")
                continue

            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_content)
            modified += 1

    print(f"Added future annotations to {modified} files")


if __name__ == "__main__":
    main()
