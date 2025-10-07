#!/usr/bin/env python3
"""
Verification script for P0-1 MessageScheduler method signature fix.

This script verifies that:
1. The new schedule_existing_message() method exists
2. All incorrect calls have been updated
3. The MessageStatus enum includes SCHEDULED and CANCELLED
4. Syntax is valid in all modified files
"""
import ast
import sys
from pathlib import Path


def check_file_syntax(file_path: Path) -> bool:
    """Check if Python file has valid syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True
    except SyntaxError as e:
        print(f"  [FAIL] Syntax error in {file_path}: {e}")
        return False


def check_method_exists(file_path: Path, method_name: str) -> bool:
    """Check if method exists in file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return f"def {method_name}" in content or f"async def {method_name}" in content
    except Exception as e:
        print(f"  [FAIL] Error reading {file_path}: {e}")
        return False


def check_no_incorrect_calls(file_path: Path, incorrect_pattern: str) -> bool:
    """Check that incorrect call pattern doesn't exist."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if incorrect_pattern in content:
                # Count occurrences
                count = content.count(incorrect_pattern)
                print(f"  [FAIL] Found {count} incorrect call(s) in {file_path}")
                return False
            return True
    except Exception as e:
        print(f"  [FAIL] Error reading {file_path}: {e}")
        return False


def check_enum_value(file_path: Path, enum_name: str, value: str) -> bool:
    """Check if enum contains specific value."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Simple pattern matching for enum values
            pattern = f'{value.upper()} = "{value.lower()}"'
            return pattern in content
    except Exception as e:
        print(f"  [FAIL] Error reading {file_path}: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("P0-1 MessageScheduler Fix Verification")
    print("=" * 70)
    print()

    base_path = Path(__file__).parent.parent / "backend-hormonia"
    all_checks_passed = True

    # Check 1: Syntax validation
    print("[OK] Check 1: Python syntax validation")
    files_to_check = [
        base_path / "app" / "services" / "message_scheduler.py",
        base_path / "app" / "services" / "flow.py",
        base_path / "app" / "models" / "message.py",
    ]

    for file_path in files_to_check:
        if file_path.exists():
            if check_file_syntax(file_path):
                print(f"  [PASS] {file_path.name} - Valid syntax")
            else:
                all_checks_passed = False
        else:
            print(f"  [FAIL] {file_path} - File not found")
            all_checks_passed = False
    print()

    # Check 2: New method exists
    print("[OK] Check 2: schedule_existing_message() method exists")
    scheduler_file = base_path / "app" / "services" / "message_scheduler.py"
    if scheduler_file.exists():
        if check_method_exists(scheduler_file, "schedule_existing_message"):
            print(f"  [PASS] Method found in {scheduler_file.name}")
        else:
            print(f"  [FAIL] Method NOT found in {scheduler_file.name}")
            all_checks_passed = False
    else:
        print(f"  [FAIL] {scheduler_file} - File not found")
        all_checks_passed = False
    print()

    # Check 3: No incorrect calls
    print("[OK] Check 3: No incorrect schedule_message() calls")
    flow_file = base_path / "app" / "services" / "flow.py"
    if flow_file.exists():
        if check_no_incorrect_calls(flow_file, "schedule_message(message_id="):
            print(f"  [PASS] No incorrect calls in {flow_file.name}")
        else:
            print(f"  [FAIL] Incorrect calls found in {flow_file.name}")
            all_checks_passed = False
    else:
        print(f"  [FAIL] {flow_file} - File not found")
        all_checks_passed = False
    print()

    # Check 4: MessageStatus enum values
    print("[OK] Check 4: MessageStatus enum includes SCHEDULED and CANCELLED")
    message_file = base_path / "app" / "models" / "message.py"
    if message_file.exists():
        scheduled_exists = check_enum_value(message_file, "MessageStatus", "scheduled")
        cancelled_exists = check_enum_value(message_file, "MessageStatus", "cancelled")

        if scheduled_exists:
            print(f"  [PASS] SCHEDULED status found in {message_file.name}")
        else:
            print(f"  [FAIL] SCHEDULED status NOT found in {message_file.name}")
            all_checks_passed = False

        if cancelled_exists:
            print(f"  [PASS] CANCELLED status found in {message_file.name}")
        else:
            print(f"  [FAIL] CANCELLED status NOT found in {message_file.name}")
            all_checks_passed = False
    else:
        print(f"  [FAIL] {message_file} - File not found")
        all_checks_passed = False
    print()

    # Check 5: Test file exists
    print("[OK] Check 5: Test file exists")
    test_file = base_path / "tests" / "test_message_scheduler_signature_fix.py"
    if test_file.exists():
        print(f"  [PASS] Test file found: {test_file.name}")
        if check_file_syntax(test_file):
            print(f"  [PASS] Test file has valid syntax")
        else:
            print(f"  [FAIL] Test file has syntax errors")
            all_checks_passed = False
    else:
        print(f"  [FAIL] Test file NOT found: {test_file}")
        all_checks_passed = False
    print()

    # Check 6: Documentation exists
    print("[OK] Check 6: Documentation exists")
    docs_path = base_path.parent / "docs" / "fixes"
    doc_files = [
        "P0-1_MESSAGE_SCHEDULER_SIGNATURE_FIX.md",
        "IMPLEMENTATION_SUMMARY_P0-1.md",
        "QUICK_REFERENCE_P0-1.md"
    ]

    for doc_file in doc_files:
        doc_path = docs_path / doc_file
        if doc_path.exists():
            print(f"  [PASS] Documentation found: {doc_file}")
        else:
            print(f"  [WARN] Documentation missing: {doc_file} (non-critical)")
    print()

    # Final summary
    print("=" * 70)
    if all_checks_passed:
        print("[SUCCESS] ALL CRITICAL CHECKS PASSED")
        print("=" * 70)
        print()
        print("Fix is ready for deployment!")
        print()
        print("Next steps:")
        print("  1. Run tests: pytest tests/test_message_scheduler_signature_fix.py -v")
        print("  2. Deploy to staging")
        print("  3. Monitor error logs for TypeErrors")
        print("  4. Verify message delivery metrics")
        return 0
    else:
        print("[ERROR] SOME CHECKS FAILED")
        print("=" * 70)
        print()
        print("Please review the errors above and fix before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
