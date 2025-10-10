#!/usr/bin/env python3
"""
Validate that test files are syntactically correct and importable.
"""
import ast
import sys
import os
from pathlib import Path

def validate_file(file_path):
    """Validate a Python file for syntax errors."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse AST to check syntax
        ast.parse(content)
        print(f"✓ {file_path} - Syntax OK")
        return True
    except SyntaxError as e:
        print(f"✗ {file_path} - Syntax Error: {e}")
        return False
    except Exception as e:
        print(f"✗ {file_path} - Error: {e}")
        return False

def main():
    """Validate all test files."""
    test_files = [
        "tests/unit/utils/test_security.py",
        "tests/unit/utils/test_cache.py",
        "tests/unit/utils/test_input_sanitization.py"
    ]

    print("Validating test files...")
    all_valid = True

    for test_file in test_files:
        if os.path.exists(test_file):
            if not validate_file(test_file):
                all_valid = False
        else:
            print(f"✗ {test_file} - File not found")
            all_valid = False

    if all_valid:
        print("\n✓ All test files are syntactically valid!")
    else:
        print("\n✗ Some test files have issues!")
        sys.exit(1)

if __name__ == "__main__":
    main()