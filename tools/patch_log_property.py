#!/usr/bin/env python3
import os
import re


def patch_base_class(root_dir):
    """Find and patch the base SpiderFootPlugin class to add a log property
    setter. This is the preferred solution as it will fix all modules at once.

    Returns True if the base class was patched, False otherwise.
    """
    # Likely base class files
    potential_files = ["sflib.py", "spiderfoot.py", "core.py"]
    base_class_pattern = re.compile(
        r"class\s+(?:SpiderFootPlugin|SpiderFootBaseModule)\s*\("
    )
    log_property_pattern = re.compile(
        r"\s+@property\s+def\s+log\s*\(\s*self\s*\)")

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file in potential_files:
                file_path = os.path.join(root, file)
                print(f"Checking {file_path} for base class...")

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if not base_class_pattern.search(content):
                        continue

                    # Check if the file has a log property without a setter
                    log_match = log_property_pattern.search(content)
                    if not log_match:
                        continue

                    has_setter = "@log.setter" in content
                    if has_setter:
                        print("Log setter already exists in base class.")
                        return True

                    # Find the log property
                    prop_start = log_match.start()
                    next_lines = content[prop_start:].split("\n")

                    # Find the property implementation
                    indentation = " " * (
                        len(next_lines[0]) - len(next_lines[0].lstrip())
                    )

                    # Find where to insert the setter (after the log property method)
                    insert_position = prop_start
                    for i, line in enumerate(next_lines):
                        insert_position += len(line) + 1  # +1 for newline
                        if (
                            i > 0 and
                            not line.strip().startswith("return") and
                            not line.strip().startswith("#")
                        ):
                            break

                    # Create setter code with the same indentation as the property
                    setter_code = f"{indentation}@log.setter\n{indentation}def log(self, value):\n"
                    setter_code += f'{indentation}    """Set the logger object - used for testing."""\n'
                    setter_code += f"{indentation}    self._log = value\n\n"

                    # Insert the setter
                    new_content = (
                        content[:insert_position] +
                        setter_code +
                        content[insert_position:]
                    )

                    # Write back to the file
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                    print(f"✅ Added log setter to base class in {file_path}")
                    return True
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")

    return False


def patch_individual_modules(root_dir):
    """Patch each individual module to add a log property setter.

    This is the fallback solution if we can't find the base class.
    """
    module_files = []
    # Find all module files
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.startswith("sfp_") and file.endswith(
                ".py"
            ):  # Changed from test_sfp_ to sfp_
                module_files.append(os.path.join(root, file))

    if not module_files:
        print("No SpiderFoot module files found!")
        return

    print(f"Found {len(module_files)} module files to check.")
    log_property_pattern = re.compile(
        r"\s+@property\s+def\s+log\s*\(\s*self\s*\)")
    patched_count = 0

    for file_path in module_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if the file has a log property without a setter
            log_match = log_property_pattern.search(content)
            if not log_match:
                continue

            has_setter = "@log.setter" in content
            if has_setter:
                continue

            # Find the log property
            prop_start = log_match.start()
            next_lines = content[prop_start:].split("\n")

            # Find the property implementation
            indentation = " " * \
                (len(next_lines[0]) - len(next_lines[0].lstrip()))

            # Find where to insert the setter (after the log property method)
            insert_position = prop_start
            for i, line in enumerate(next_lines):
                insert_position += len(line) + 1  # +1 for newline
                if (
                    i > 0 and
                    not line.strip().startswith("return") and
                    not line.strip().startswith("#")
                ):
                    break

            # Create setter code with the same indentation as the property
            setter_code = (
                f"{indentation}@log.setter\n{indentation}def log(self, value):\n"
            )
            setter_code += (
                f'{indentation}    """Set the logger object - used for testing."""\n'
            )
            setter_code += f"{indentation}    self._log = value\n\n"

            # Insert the setter
            new_content = (
                content[:insert_position] +
                setter_code + content[insert_position:]
            )

            # Write back to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            patched_count += 1
            print(f"✅ Patched {file_path}")

        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    print(f"Patched {patched_count} module files.")


def main():
    """Main entry point for the script."""
    root_dir = os.path.dirname(os.path.abspath(__file__))

    # Try to patch base class first
    base_patched = patch_base_class(root_dir)
    if base_patched:
        print("Base class patched successfully.")
    else:
        print("Could not patch base class.")

    # Always force individual module patching
    print("Forcing individual module patching...")
    patch_individual_modules(root_dir)

    print("\nDone! Try running your tests again.")
    print("If tests still fail, you may need to manually fix some modules.")


if __name__ == "__main__":
    main()
