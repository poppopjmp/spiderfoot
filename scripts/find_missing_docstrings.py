"""Find public functions missing docstrings in critical spiderfoot/ files."""
from __future__ import annotations

import ast
import os


PRIORITY_FILES = [
    'spiderfoot/sflib/core.py',
    'spiderfoot/helpers.py',
    'spiderfoot/db/db.py',
    'spiderfoot/scan_service/scanner.py',
    'spiderfoot/correlation/rule_executor.py',
    'spiderfoot/correlation/rule_loader.py',
    'spiderfoot/correlation/result_aggregator.py',
    'spiderfoot/correlation/event_enricher.py',
    'spiderfoot/webui/routes.py',
    'spiderfoot/webui/scan.py',
    'spiderfoot/webui/export.py',
    'spiderfoot/webui/helpers.py',
    'spiderfoot/webui/settings.py',
    'spiderfoot/webui/info.py',
    'spiderfoot/webui/templates.py',
    'spiderfoot/webui/workspace.py',
    'spiderfoot/api/routers/scan.py',
    'spiderfoot/api/routers/data.py',
    'spiderfoot/api/routers/workspace.py',
    'spiderfoot/cli_service.py',
]


def main():
    total = 0
    for filepath in PRIORITY_FILES:
        if not os.path.exists(filepath):
            continue
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        missing = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private/dunder
                if node.name.startswith('_') and not node.name.startswith('__'):
                    continue
                has_doc = (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )
                if not has_doc:
                    missing.append((node.lineno, node.name))

        if missing:
            print(f"\n{filepath} ({len(missing)} public functions without docstrings):")
            for lineno, name in missing[:8]:
                print(f"  L{lineno}: {name}")
            if len(missing) > 8:
                print(f"  ... and {len(missing) - 8} more")
            total += len(missing)

    print(f"\nTotal: {total} public functions missing docstrings in priority files")


if __name__ == '__main__':
    main()
