#!/usr/bin/env python3
"""
Fix remaining class Config declarations in migrated schema files.
Converts all `class Config:` to `model_config = ConfigDict(...)`.
"""
import re
import sys
from pathlib import Path

# Files already migrated
FILES_TO_FIX = [
    "app/schemas/v2/ai.py",
    "app/schemas/v2/alerts.py",
    "app/schemas/v2/appointment.py",
    "app/schemas/v2/auth.py",
    "app/schemas/v2/common.py",
    "app/schemas/v2/dashboard.py",
    "app/schemas/v2/debug.py",
    "app/schemas/v2/localization.py",
]

def fix_config_class(content: str) -> str:
    """
    Replace 'class Config:' patterns with 'model_config = ConfigDict(...)'.
    Handles both from_attributes and json_schema_extra patterns.
    """
    # Pattern 1: Config with from_attributes = True
    pattern1 = r'(\s+)class Config:\s+from_attributes = True'
    replacement1 = r'\1model_config = ConfigDict(from_attributes=True)'
    content = re.sub(pattern1, replacement1, content)

    # Pattern 2: Config with json_schema_extra only
    # Match: class Config:\n        json_schema_extra = {
    pattern2 = r'(\s+)class Config:\s+json_schema_extra = (\{)'
    replacement2 = r'\1model_config = ConfigDict(\n\1    json_schema_extra = \2'
    content = re.sub(pattern2, replacement2, content)

    # Pattern 3: Config with both from_attributes and json_schema_extra
    # This is rare but handle it
    pattern3 = r'(\s+)class Config:\s+from_attributes = True\s+json_schema_extra = (\{)'
    replacement3 = r'\1model_config = ConfigDict(\n\1    from_attributes=True,\n\1    json_schema_extra = \2'
    content = re.sub(pattern3, replacement3, content)

    # Now we need to close the ConfigDict parenthesis
    # Find all model_config = ConfigDict( and match closing braces
    lines = content.split('\n')
    new_lines = []
    in_model_config = False
    brace_count = 0
    indent = ''

    for i, line in enumerate(lines):
        if 'model_config = ConfigDict(' in line:
            in_model_config = True
            # Extract indent from this line
            indent = line[:len(line) - len(line.lstrip())]
            brace_count = 0
            new_lines.append(line)
            continue

        if in_model_config:
            # Count braces
            brace_count += line.count('{') - line.count('}')
            new_lines.append(line)

            # When we close all braces, close ConfigDict too
            if brace_count == 0 and ('}' in line):
                # Add closing parenthesis on next line with same indent
                new_lines.append(f'{indent})')
                in_model_config = False
        else:
            new_lines.append(line)

    return '\n'.join(new_lines)

def main():
    base_dir = Path(__file__).parent.parent

    for file_path in FILES_TO_FIX:
        full_path = base_dir / file_path
        if not full_path.exists():
            print(f"Warning: {file_path} not found, skipping...")
            continue

        print(f"Processing {file_path}...")

        # Read file
        content = full_path.read_text(encoding='utf-8')

        # Fix configs
        fixed_content = fix_config_class(content)

        # Write back
        full_path.write_text(fixed_content, encoding='utf-8')
        print(f"  ✓ Fixed {file_path}")

    print("\nAll files processed!")

if __name__ == "__main__":
    main()
