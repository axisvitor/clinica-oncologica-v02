#!/usr/bin/env python3
"""
Validation script for remaining role enum fixes.
Validates that SUPER_ADMIN references are removed and role enums are used correctly.
"""
import ast
import os
import sys
from pathlib import Path

def check_file_for_super_admin(file_path: Path) -> list:
    """Check if file contains SUPER_ADMIN references."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'SUPER_ADMIN' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if 'SUPER_ADMIN' in line:
                    issues.append(f"Line {i}: {line.strip()}")
    except Exception as e:
        issues.append(f"Error reading file: {e}")
    
    return issues

def check_file_for_string_role_comparison(file_path: Path) -> list:
    """Check if file uses string-based role comparisons instead of enum."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for patterns like user.role == "admin" or user_type in ["medico", "admin"]
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            if (('user_type' in line_lower and ('medico' in line_lower or 'admin' in line_lower)) or
                ('role ==' in line_lower and ('"admin"' in line_lower or '"doctor"' in line_lower))):
                issues.append(f"Line {i}: {line.strip()}")
    except Exception as e:
        issues.append(f"Error reading file: {e}")
    
    return issues

def validate_business_dependencies():
    """Validate business_dependencies.py fixes."""
    file_path = Path("app/dependencies/business_dependencies.py")
    print(f"Checking {file_path}...")
    
    issues = check_file_for_super_admin(file_path)
    if issues:
        print("❌ SUPER_ADMIN references found:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("✅ No SUPER_ADMIN references found")
        return True

def validate_quiz_alerts():
    """Validate quiz_alerts.py fixes."""
    file_path = Path("app/api/v1/quiz_alerts.py")
    print(f"Checking {file_path}...")
    
    # Check for string-based role comparisons
    issues = check_file_for_string_role_comparison(file_path)
    if issues:
        print("❌ String-based role comparisons found:")
        for issue in issues:
            print(f"  {issue}")
        return False
    
    # Check that UserRole is imported
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'from app.models.user import User, UserRole' not in content:
            print("❌ UserRole not properly imported")
            return False
        
        if 'UserRole.DOCTOR' not in content or 'UserRole.ADMIN' not in content:
            print("❌ UserRole enum not used in authorization checks")
            return False
        
        print("✅ UserRole enum properly imported and used")
        return True
        
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False

def validate_import_fix():
    """Validate that get_db import is correct."""
    file_path = Path("app/api/v1/quiz_alerts.py")
    print(f"Checking imports in {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'from app.database import get_db' in content:
            print("✅ get_db import is correct")
            return True
        else:
            print("❌ get_db import is incorrect")
            return False
            
    except Exception as e:
        print(f"❌ Error checking imports: {e}")
        return False

def main():
    """Main validation function."""
    print("🔍 Validating remaining role enum fixes...")
    print("=" * 50)
    
    # Change to backend directory
    os.chdir(Path(__file__).parent.parent)
    
    all_passed = True
    
    # Validate business dependencies
    if not validate_business_dependencies():
        all_passed = False
    
    print()
    
    # Validate quiz alerts
    if not validate_quiz_alerts():
        all_passed = False
    
    print()
    
    # Validate imports
    if not validate_import_fix():
        all_passed = False
    
    print()
    print("=" * 50)
    
    if all_passed:
        print("✅ All validations passed! Remaining fixes are complete.")
        return 0
    else:
        print("❌ Some validations failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())