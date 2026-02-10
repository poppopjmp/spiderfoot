"""Categorize print() calls: in __main__ blocks vs runtime code."""
from __future__ import annotations

import ast
import os


def main():
    main_prints = []
    runtime_prints = []

    for root, dirs, files in os.walk('spiderfoot'):
        dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                content = fh.read()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            # Find __main__ guard line ranges
            main_ranges = []
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    # Check for if __name__ == "__main__"
                    test = node.test
                    if (isinstance(test, ast.Compare)
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.Eq)):
                        left = test.left
                        right = test.comparators[0] if test.comparators else None
                        if (isinstance(left, ast.Name) and left.id == '__name__'
                            and isinstance(right, ast.Constant) and right.value == '__main__'):
                            end = getattr(node, 'end_lineno', node.lineno + 100)
                            main_ranges.append((node.lineno, end))

            def in_main(lineno):
                return any(start <= lineno <= end for start, end in main_ranges)

            # Find all print calls
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    func = node.value.func
                    if isinstance(func, ast.Name) and func.id == 'print':
                        if in_main(node.lineno):
                            main_prints.append(f"{path}:{node.lineno}")
                        else:
                            runtime_prints.append(f"{path}:{node.lineno}")

    print(f"print() in __main__ blocks: {len(main_prints)}")
    print(f"print() in runtime code: {len(runtime_prints)}")
    print("\n=== Runtime print() calls ===")
    for loc in runtime_prints:
        print(f"  {loc}")


if __name__ == '__main__':
    main()
