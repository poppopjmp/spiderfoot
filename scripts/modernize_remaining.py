#!/usr/bin/env python3
"""Add from __future__ import annotations and modernize old typing generics."""
import ast
import re
import sys

OLD_TYPING_SYMBOLS = {
    "Dict", "List", "Optional", "Tuple", "Set", "FrozenSet",
    "Type", "Union", "Deque", "DefaultDict", "Sequence",
}

TARGET_FILES = [
    "scripts/migrate_all_threadreaper.py",
    "scripts/migrate_threadreaper.py",
    "spiderfoot/api/versioning.py",
    "spiderfoot/cli/commands/interactive.py",
    "spiderfoot/core/performance.py",
    "spiderfoot/core/security.py",
    "spiderfoot/db/repositories/base.py",
    "spiderfoot/db/repositories/config_repository.py",
    "spiderfoot/mcp_integration.py",
    "spiderfoot/rate_limiting.py",
    "spiderfoot/security_integration.py",
    "spiderfoot/security_middleware.py",
    "spiderfoot/service_integration.py",
    "spiderfoot/service_runner.py",
    "spiderfoot/workspace.py",
    "test/unit/modules/test_sfp__stor_db_advanced.py",
    "test/unit/test_context_window.py",
    "test/unit/test_final_db_purge.py",
    "test/unit/test_scan_service_phase2.py",
    "test/unit/utils/leak_detector.py",
    "test/unit/utils/platform_utils.py",
    "test/unit/utils/resource_manager.py",
    "test/unit/utils/test_module_base.py",
    "test/unit/utils/thread_registry.py",
    "test/utils/legacy_test_helpers.py",
    "update_version.py",
]


def add_future_import(content: str) -> str:
    """Add 'from __future__ import annotations' after initial comments/docstrings."""
    if "from __future__ import annotations" in content:
        return content

    lines = content.split("\n")
    insert_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            insert_idx = i + 1
        elif stripped.startswith('"""') or stripped.startswith("'''"):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 3:
                # Single-line docstring
                insert_idx = i + 1
            else:
                # Multi-line docstring
                for j in range(i + 1, len(lines)):
                    if quote in lines[j]:
                        insert_idx = j + 1
                        break
        else:
            break

    lines.insert(insert_idx, "from __future__ import annotations")
    if insert_idx < len(lines) - 1 and lines[insert_idx + 1].strip():
        lines.insert(insert_idx + 1, "")
    return "\n".join(lines)


def modernize_typing(content: str) -> str:
    """Replace old typing generics with modern equivalents."""
    # Dict[X] -> dict[X], List[X] -> list[X], etc.
    simple_map = {
        "Dict": "dict", "List": "list", "Tuple": "tuple",
        "Set": "set", "FrozenSet": "frozenset", "Type": "type",
    }
    for old, new in simple_map.items():
        content = re.sub(
            r"(?<![A-Za-z_0-9.])" + old + r"\[", new + "[", content
        )

    # Optional[X] -> X | None (simple non-nested)
    while True:
        m = re.search(r"(?<![A-Za-z_0-9.])Optional\[([^\[\]]+)\]", content)
        if not m:
            break
        content = content[: m.start()] + m.group(1) + " | None" + content[m.end() :]

    # Union[X, Y] -> X | Y (simple non-nested)
    while True:
        m = re.search(r"(?<![A-Za-z_0-9.])Union\[([^\[\]]+)\]", content)
        if not m:
            break
        parts = [p.strip() for p in m.group(1).split(",")]
        content = content[: m.start()] + " | ".join(parts) + content[m.end() :]

    return content


def clean_typing_import(content: str) -> str:
    """Remove unused old typing symbols from the import line."""
    typing_m = re.search(r"^from typing import (.+?)$", content, re.MULTILINE)
    if not typing_m:
        return content

    import_text = typing_m.group(1).strip().strip("()")
    symbols = [s.strip() for s in import_text.split(",") if s.strip()]

    keep = []
    for sym in symbols:
        if sym not in OLD_TYPING_SYMBOLS:
            keep.append(sym)
        else:
            # Check if still used in the rest of the content
            rest = content[typing_m.end() :]
            if re.search(
                r"(?<![A-Za-z_0-9])" + re.escape(sym) + r"(?![A-Za-z_0-9])", rest
            ):
                keep.append(sym)

    if keep:
        new_import = "from typing import " + ", ".join(keep)
    else:
        new_import = ""

    if new_import:
        content = content[: typing_m.start()] + new_import + content[typing_m.end() :]
    else:
        # Remove entire line including newline
        end = typing_m.end()
        if end < len(content) and content[end] == "\n":
            end += 1
        content = content[: typing_m.start()] + content[end:]

    return content


def main() -> None:
    modified = 0
    for path in TARGET_FILES:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"SKIP (not found): {path}")
            continue

        original = content
        content = add_future_import(content)
        content = modernize_typing(content)
        content = clean_typing_import(content)

        if content != original:
            try:
                ast.parse(content)
            except SyntaxError as e:
                print(f"SKIP (syntax error): {path}: {e}")
                continue
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            modified += 1
            print(f"OK: {path}")
        else:
            print(f"SKIP (no changes): {path}")

    print(f"\nModified: {modified}/{len(TARGET_FILES)}")


if __name__ == "__main__":
    main()
