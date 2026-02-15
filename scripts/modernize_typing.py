#!/usr/bin/env python3
"""Modernize typing imports in the SpiderFoot project.

For every file that contains ``from __future__ import annotations``, this
script replaces legacy ``typing`` generics and wrappers with their modern
PEP 585 / PEP 604 equivalents:

    Dict[K, V]      →  dict[K, V]
    List[T]          →  list[T]
    Tuple[T, ...]    →  tuple[T, ...]
    Set[T]           →  set[T]
    Optional[T]      →  T | None
    Union[X, Y]      →  X | Y

Afterwards it removes the now-unused symbols from ``from typing import …``
and deletes the import line entirely when nothing remains.

Usage
-----
    python scripts/modernize_typing.py            # apply changes
    python scripts/modernize_typing.py --dry-run   # preview only
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from pathlib import Path

# ── configuration ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIRS = ["spiderfoot", "modules"]

SIMPLE_TYPE_MAP: dict[str, str] = {
    "Dict": "dict",
    "List": "list",
    "Tuple": "tuple",
    "Set": "set",
}

REMOVABLE_SYMBOLS: set[str] = {
    "Dict", "List", "Tuple", "Set", "Optional", "Union",
}

# ── file discovery ───────────────────────────────────────────────────────────


def find_python_files() -> list[Path]:
    """Return sorted .py files under *TARGET_DIRS*, skipping ``*_pb2.py``."""
    files: list[Path] = []
    for name in TARGET_DIRS:
        d = PROJECT_ROOT / name
        if d.is_dir():
            for p in sorted(d.rglob("*.py")):
                if "_pb2" not in p.stem:
                    files.append(p)
    return files


# ── protected-region helpers (string literals only) ──────────────────────────


def _get_string_regions(source: str) -> list[tuple[int, int]]:
    """Return *(start, end)* char-offset spans for every string literal.

    Comments are intentionally **not** protected so that ``# type:`` comments
    are modernised as well.
    """
    regions: list[tuple[int, int]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return regions

    # Build a table of cumulative character offsets per source line.
    lines = source.splitlines(True)
    line_starts = [0]
    for ln in lines:
        line_starts.append(line_starts[-1] + len(ln))

    for tok in tokens:
        if tok.type == tokenize.STRING:
            sr, sc = tok.start
            er, ec = tok.end
            regions.append((line_starts[sr - 1] + sc, line_starts[er - 1] + ec))

    regions.sort()
    return regions


def _in_string(pos: int, length: int, regions: list[tuple[int, int]]) -> bool:
    """Return *True* if **[pos, pos+length)** overlaps any string region."""
    end = pos + length
    for rs, re_ in regions:
        if rs >= end:
            return False
        if re_ > pos:
            return True
    return False


# ── bracket / comma helpers ──────────────────────────────────────────────────


def _find_closing_bracket(text: str, open_pos: int) -> int:
    """Return index of the ``]`` matching the ``[`` at *open_pos*, or ``-1``."""
    depth = 1
    i = open_pos + 1
    while i < len(text):
        ch = text[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_level(text: str) -> list[str]:
    """Split *text* by commas that are **not** inside any brackets."""
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in text:
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf.clear()
        else:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


# ── Phase 1 – simple generic replacements ────────────────────────────────────


def _replace_simple_types(source: str) -> tuple[str, dict[str, int]]:
    """``Dict[`` → ``dict[``, ``List[`` → ``list[``, etc."""
    stats: dict[str, int] = {}
    for old_name, new_name in SIMPLE_TYPE_MAP.items():
        pat = re.compile(r"(?<![A-Za-z_0-9])" + re.escape(old_name) + r"\[")
        regions = _get_string_regions(source)
        hits: list[tuple[int, int, str]] = []
        for m in pat.finditer(source):
            if not _in_string(m.start(), m.end() - m.start(), regions):
                hits.append((m.start(), m.end(), new_name + "["))
        if hits:
            stats[old_name] = len(hits)
            # Apply from end → start so earlier offsets stay valid.
            for s, e, repl in reversed(hits):
                source = source[:s] + repl + source[e:]
    return source, stats


# ── Phase 2 – Optional[X] → X | None ────────────────────────────────────────


def _replace_optional(source: str) -> tuple[str, int]:
    pat = re.compile(r"(?<![A-Za-z_0-9])Optional\[")
    count = 0
    while True:
        regions = _get_string_regions(source)
        found = False
        for m in pat.finditer(source):
            if _in_string(m.start(), m.end() - m.start(), regions):
                continue
            close = _find_closing_bracket(source, m.end() - 1)
            if close == -1:
                continue
            inner = source[m.end():close].strip()
            source = source[:m.start()] + inner + " | None" + source[close + 1:]
            count += 1
            found = True
            break  # positions shifted – restart search
        if not found:
            break
    return source, count


# ── Phase 3 – Union[X, Y] → X | Y ───────────────────────────────────────────


def _replace_union(source: str) -> tuple[str, int]:
    pat = re.compile(r"(?<![A-Za-z_0-9])Union\[")
    count = 0
    while True:
        regions = _get_string_regions(source)
        found = False
        for m in pat.finditer(source):
            if _in_string(m.start(), m.end() - m.start(), regions):
                continue
            close = _find_closing_bracket(source, m.end() - 1)
            if close == -1:
                continue
            inner = source[m.end():close]
            parts = _split_top_level(inner)
            if len(parts) < 2:
                continue  # degenerate Union[X] – leave it
            replacement = " | ".join(parts)
            source = source[:m.start()] + replacement + source[close + 1:]
            count += 1
            found = True
            break
        if not found:
            break
    return source, count


# ── Phase 4 – clean up ``from typing import …`` ─────────────────────────────


def _find_typing_import(source: str):
    """Locate the first ``from typing import …`` statement.

    Returns ``(start, end, names)`` or ``None``.

    * *start* / *end* – character offsets spanning the full statement
      **including** the trailing newline (if any).
    * *names* – list of imported symbol strings (aliases stripped).
    """
    m = re.search(r"^from\s+typing\s+import\s+", source, re.MULTILINE)
    if m is None:
        return None

    abs_start = m.start()
    rest = source[m.end():]

    # ── parenthesised (possibly multi-line) ──
    if rest.startswith("("):
        close = rest.find(")")
        if close == -1:
            return None
        inner = rest[1:close]
        abs_end = m.end() + close + 1
        if abs_end < len(source) and source[abs_end] == "\n":
            abs_end += 1
        names = [
            cleaned
            for raw in re.split(r"[,\n]", inner)
            if (cleaned := re.sub(r"\s*#.*", "", raw).strip())
        ]
        return abs_start, abs_end, names

    # ── single physical line (handle backslash continuation) ──
    eol = source.find("\n", m.end())
    abs_end = (eol + 1) if eol != -1 else len(source)
    line_text = source[m.end(): eol if eol != -1 else len(source)]

    while line_text.rstrip().endswith("\\"):
        line_text = line_text.rstrip().rstrip("\\")
        next_eol = source.find("\n", abs_end)
        if next_eol == -1:
            line_text += " " + source[abs_end:].strip()
            abs_end = len(source)
            break
        line_text += " " + source[abs_end:next_eol].strip()
        abs_end = next_eol + 1

    # Strip any trailing inline comment.
    line_text = re.sub(r"\s*#.*", "", line_text)
    names = [n.strip() for n in line_text.split(",") if n.strip()]
    return abs_start, abs_end, names


def _symbol_used_outside(source: str, symbol: str, imp_start: int, imp_end: int) -> bool:
    """Return *True* if *symbol* is referenced outside the import span."""
    outside = source[:imp_start] + source[imp_end:]
    return bool(
        re.search(r"(?<![A-Za-z_0-9])" + re.escape(symbol) + r"(?![A-Za-z_0-9])", outside)
    )


def _clean_typing_imports(source: str) -> tuple[str, list[str]]:
    """Remove now-unused typing symbols and drop empty import lines."""
    all_removed: list[str] = []

    for _ in range(20):  # safety bound
        info = _find_typing_import(source)
        if info is None:
            break
        imp_start, imp_end, names = info

        keep = [
            n for n in names
            if n not in REMOVABLE_SYMBOLS
            or _symbol_used_outside(source, n, imp_start, imp_end)
        ]
        drop = [n for n in names if n not in keep]

        if not drop:
            break  # nothing removable in this import → done

        all_removed.extend(drop)

        if not keep:
            # Delete the entire import line.
            source = source[:imp_start] + source[imp_end:]
        else:
            new_line = "from typing import " + ", ".join(keep) + "\n"
            source = source[:imp_start] + new_line + source[imp_end:]
        # Loop again: the removal may expose the *next* ``from typing import``
        # (or the same one may still have removable symbols if names shifted).

    return source, all_removed


# ── per-file orchestration ───────────────────────────────────────────────────


def process_file(path: Path, *, dry_run: bool = False) -> tuple[bool, list[str]]:
    """Modernise a single file.  Returns ``(was_modified, log_lines)``."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return False, [f"  ERROR reading: {exc}"]

    if "from __future__ import annotations" not in original:
        return False, []

    source = original
    log: list[str] = []

    # 1. Dict[->dict[, List[->list[, ...
    source, simple_stats = _replace_simple_types(source)
    for name, cnt in simple_stats.items():
        log.append(f"  {name}[ -> {SIMPLE_TYPE_MAP[name]}[  ({cnt})")

    # 2. Optional[X] -> X | None
    source, n_opt = _replace_optional(source)
    if n_opt:
        log.append(f"  Optional[X] -> X | None  ({n_opt})")

    # 3. Union[X, Y] -> X | Y
    source, n_union = _replace_union(source)
    if n_union:
        log.append(f"  Union[X, Y] -> X | Y  ({n_union})")

    # 4. Clean up typing imports
    source, removed = _clean_typing_imports(source)
    if removed:
        log.append(f"  Removed from typing import: {', '.join(removed)}")

    if source != original:
        if not dry_run:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(source)
        return True, log

    return False, log


# ── entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Modernize typing imports in SpiderFoot "
                    "(Dict->dict, Optional->X|None, Union->X|Y)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing any files",
    )
    args = parser.parse_args()

    files = find_python_files()
    print(f"Scanning {len(files)} Python files ...")
    if args.dry_run:
        print("(dry-run mode -- no files will be modified)\n")

    n_modified = 0
    n_with_future = 0

    for path in files:
        modified, log = process_file(path, dry_run=args.dry_run)
        rel = path.relative_to(PROJECT_ROOT)

        if modified:
            n_modified += 1
            n_with_future += 1
            label = "Would modify" if args.dry_run else "Modified"
            print(f"\n{label}: {rel}")
            for line in log:
                print(line)
        elif log:
            # File has ``from __future__ import annotations`` but needed no changes.
            n_with_future += 1

    print(f"\n{'=' * 60}")
    print(f"  Files scanned          : {len(files)}")
    print(f"  With future annotations: {n_with_future}")
    action = "Would modify" if args.dry_run else "Modified"
    print(f"  {action:22s}: {n_modified}")
    print("=" * 60)


if __name__ == "__main__":
    main()
