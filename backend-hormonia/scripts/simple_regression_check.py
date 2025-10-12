#!/usr/bin/env python3
"""
Simple Regression Check - Core validations without complex imports.
Focuses on the most critical patterns that must not regress.
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

def check_file_patterns(file_path: Path, patterns: Dict[str, str]) -> Dict[str, bool]:
    """Check file for specific patterns. Returns dict of pattern_name -> found_status."""
    results = {}
    
    if not file_path.exists():
        return {name: False for name in patterns.keys()}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for pattern_name, pattern in patterns.items():
            if pattern.startswith('NOT:'):
                # Pattern should NOT be found
                actual_pattern = pattern[4:]
                found = bool(re.search(actual_pattern, content, re.IGNORECASE))
                results[pattern_name] = not found  # Success if NOT found
            else:
                # Pattern SHOULD be found
                found = bool(re.search(pattern, content, re.IGNORECASE))
                results[pattern_name] = found
                
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {name: False for name in patterns.keys()}
    
    return results

def main():
    """Main regression check."""
    print("🛡️  SIMPLE REGRESSION CHECK")
    print("=" * 50)
    
    all_passed = True
    
    # Critical file checks
    checks = [
        {
            'file': 'app/dependencies/business_dependencies.py',
            'description': 'Business Dependencies',
            'patterns': {
                'no_super_admin': 'NOT:SUPER_ADMIN',
                'has_yield_from': r'yield\s+from',
                'uses_admin_enum': r'UserRole\.ADMIN'
            }
        },
        {
            'file': 'app/api/v1/quiz_alerts.py', 
            'description': 'Quiz Alerts API',
            'patterns': {
                'no_super_admin': 'NOT:SUPER_ADMIN',
                'no_string_roles': 'NOT:user_type.*medico',
                'uses_role_enum': r'UserRole\.(DOCTOR|ADMIN)',
                'correct_import': r'from app\.database import get_db'
            }
        },
        {
            'file': 'app/api/v1/analytics.py',
            'description': 'Analytics API', 
            'patterns': {
                'no_super_admin': 'NOT:SUPER_ADMIN',
                'uses_admin_enum': r'UserRole\.ADMIN'
            }
        },
        {
            'file': 'app/api/v1/monthly_quiz.py',
            'description': 'Monthly Quiz API',
            'patterns': {
                'no_string_comparison': 'NOT:role.*==.*"admin"',
                'uses_enum_comparison': r'UserRole\.(ADMIN|DOCTOR)'
            }
        }
    ]
    
    print("🔍 Checking Critical Files:")
    
    for check in checks:
        file_path = Path(check['file'])
        print(f"\n📁 {check['description']} ({check['file']}):")
        
        if not file_path.exists():
            print(f"   ❌ File not found")
            all_passed = False
            continue
        
        results = check_file_patterns(file_path, check['patterns'])
        
        for pattern_name, passed in results.items():
            status = "✅" if passed else "❌"
            readable_name = pattern_name.replace('_', ' ').title()
            print(f"   {status} {readable_name}")
            if not passed:
                all_passed = False
    
    # Check for critical imports and dependencies
    print(f"\n🔍 Import and Structure Checks:")
    
    import_checks = [
        {
            'file': 'app/models/user.py',
            'pattern': r'class UserRole.*Enum',
            'description': 'UserRole Enum Exists'
        },
        {
            'file': 'app/core/date_utils.py', 
            'pattern': r'def coerce_to_date',
            'description': 'Date Coercion Function Exists'
        },
        {
            'file': 'app/core/error_handler.py',
            'pattern': r'class.*ErrorHandler',
            'description': 'Error Handler Class Exists'
        }
    ]
    
    for check in import_checks:
        file_path = Path(check['file'])
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                found = bool(re.search(check['pattern'], content))
                status = "✅" if found else "❌"
                print(f"   {status} {check['description']}")
                if not found:
                    all_passed = False
            except Exception:
                print(f"   ❌ {check['description']} (read error)")
                all_passed = False
        else:
            print(f"   ❌ {check['description']} (file not found)")
            all_passed = False
    
    # Summary
    print(f"\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL CRITICAL CHECKS PASSED!")
        print("   ✅ No SUPER_ADMIN references in critical files")
        print("   ✅ Role enums used correctly")
        print("   ✅ Dependency injection fixed")
        print("   ✅ Core utilities present")
        print("   🚀 System ready for deployment")
        return 0
    else:
        print("❌ CRITICAL CHECKS FAILED!")
        print("   🚫 Deployment should be blocked")
        print("   🔧 Fix issues above before proceeding")
        return 1

if __name__ == "__main__":
    exit(main())