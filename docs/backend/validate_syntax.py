#!/usr/bin/env python3
"""
Validate Python syntax for refactored CORS configuration files.
"""
import ast
import sys
from pathlib import Path

def validate_file(file_path: str) -> bool:
    """Validate Python syntax by parsing AST."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        print(f"✅ {file_path}: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"❌ {file_path}: Syntax Error")
        print(f"   Line {e.lineno}: {e.msg}")
        print(f"   {e.text}")
        return False
    except Exception as e:
        print(f"❌ {file_path}: Error - {e}")
        return False

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent

    files_to_validate = [
        project_root / "backend-hormonia" / "app" / "config.py",
        project_root / "backend-hormonia" / "app" / "core" / "middleware_setup.py"
    ]

    all_valid = True
    for file_path in files_to_validate:
        if not validate_file(str(file_path)):
            all_valid = False

    if all_valid:
        print("\n✅ All files have valid Python syntax!")
        sys.exit(0)
    else:
        print("\n❌ Syntax validation failed!")
        sys.exit(1)
