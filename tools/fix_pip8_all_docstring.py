import os
import subprocess


def fix_pep8_recursively(directory):
    """Fixes PEP 8 violations and docstrings recursively."""

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                print(f"Checking/Fixing: {filepath}")

                # Black (for overall formatting)
                try:
                    subprocess.run(["black", filepath],
                                   check=True, capture_output=True)
                    print("  - Black applied.")
                except subprocess.CalledProcessError as e:
                    print(f"  - Black failed: {e.stderr.decode()}")

                # Ruff (for specific fixes)
                try:
                    subprocess.run(
                        ["ruff", "check", "--fix", filepath],
                        check=True,
                        capture_output=True,
                    )
                    print("  - Ruff applied.")
                except subprocess.CalledProcessError as e:
                    print(f"  - Ruff failed: {e.stderr.decode()}")

                # autopep8 (for remaining issues)
                try:
                    subprocess.run(
                        ["autopep8", "--in-place", filepath],
                        check=True,
                        capture_output=True,
                    )
                    print("  - autopep8 applied.")
                except subprocess.CalledProcessError as e:
                    print(f"  - autopep8 failed: {e.stderr.decode()}")

                # docformatter (for docstring formatting)
                # try:
                #    subprocess.run(["docformatter", "--in-place", filepath], check=True, capture_output=True)
                #    print(f"  - docformatter applied.")
                # except subprocess.CalledProcessError as e:
                #    print(f"  - docformatter failed: {e.stderr.decode()}")


if __name__ == "__main__":
    target_directory = "."
    fix_pep8_recursively(target_directory)
