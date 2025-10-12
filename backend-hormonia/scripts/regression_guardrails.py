#!/usr/bin/env python3
"""
Regression Guardrails - Comprehensive validation for CI/CD pipeline.
Prevents regression of critical fixes and maintains system health.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_validation_script(script_path: str, description: str) -> Tuple[bool, str]:
    """Run a validation script and return success status and output."""
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, f"Failed to run {script_path}: {e}"

def check_critical_patterns() -> Dict[str, bool]:
    """Check for critical code patterns that should not regress."""
    checks = {}
    
    # Check for SUPER_ADMIN in critical files
    critical_files = [
        "app/dependencies/business_dependencies.py",
        "app/api/v1/quiz_alerts.py",
        "app/api/v1/analytics.py",
        "app/api/v1/monthly_quiz.py"
    ]
    
    for file_path in critical_files:
        full_path = Path(file_path)
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    has_super_admin = 'SUPER_ADMIN' in content
                    checks[f"no_super_admin_{file_path.replace('/', '_')}"] = not has_super_admin
            except Exception:
                checks[f"no_super_admin_{file_path.replace('/', '_')}"] = False
        else:
            checks[f"no_super_admin_{file_path.replace('/', '_')}"] = False
    
    # Check for string-based role comparisons
    role_check_files = [
        "app/api/v1/quiz_alerts.py",
        "app/api/v1/monthly_quiz.py"
    ]
    
    for file_path in role_check_files:
        full_path = Path(file_path)
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for problematic patterns
                    has_string_roles = (
                        'user_type' in content.lower() and 
                        ('medico' in content.lower() or '"admin"' in content.lower())
                    )
                    checks[f"no_string_roles_{file_path.replace('/', '_')}"] = not has_string_roles
            except Exception:
                checks[f"no_string_roles_{file_path.replace('/', '_')}"] = False
        else:
            checks[f"no_string_roles_{file_path.replace('/', '_')}"] = False
    
    return checks

def main():
    """Main regression guardrails validation."""
    print("🛡️  REGRESSION GUARDRAILS - CRITICAL VALIDATION")
    print("=" * 60)
    
    all_passed = True
    results = []
    
    # 1. Run existing validation scripts
    validation_scripts = [
        ("scripts/validate_remaining_fixes.py", "Role Enum Fixes"),
        ("scripts/validate_critical_fixes.py", "Critical Bug Fixes"),
        ("scripts/validate_dependency_injection.py", "Dependency Injection"),
        ("scripts/validate_role_enums.py", "Role Enum Consistency"),
        ("scripts/validate_date_parameters.py", "Date Parameter Handling"),
        ("scripts/validate_db_models.py", "Database Model Compatibility")
    ]
    
    print("🔍 Running Validation Scripts:")
    for script_path, description in validation_scripts:
        if Path(script_path).exists():
            success, output = run_validation_script(script_path, description)
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   {status} {description}")
            results.append((description, success, output))
            if not success:
                all_passed = False
        else:
            print(f"   ⚠️  SKIP {description} (script not found)")
    
    # 2. Run database health check
    print(f"\n🔍 Database Health Check:")
    if Path("sql/comprehensive_db_check.py").exists():
        success, output = run_validation_script("sql/comprehensive_db_check.py", "Database Health")
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} Database Health Check")
        results.append(("Database Health", success, output))
        if not success:
            all_passed = False
    else:
        print(f"   ⚠️  SKIP Database Health (script not found)")
    
    # 3. Check critical code patterns
    print(f"\n🔍 Critical Code Pattern Checks:")
    pattern_checks = check_critical_patterns()
    for check_name, passed in pattern_checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        readable_name = check_name.replace('_', ' ').title()
        print(f"   {status} {readable_name}")
        if not passed:
            all_passed = False
    
    # 4. Summary
    print(f"\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL REGRESSION GUARDRAILS PASSED!")
        print("   System is ready for deployment")
        return 0
    else:
        print("❌ REGRESSION GUARDRAILS FAILED!")
        print("   Critical issues detected - deployment blocked")
        
        # Show detailed failures
        print(f"\n📋 Failure Details:")
        for description, success, output in results:
            if not success:
                print(f"\n❌ {description}:")
                print(f"   {output[:200]}..." if len(output) > 200 else f"   {output}")
        
        for check_name, passed in pattern_checks.items():
            if not passed:
                readable_name = check_name.replace('_', ' ').title()
                print(f"\n❌ {readable_name}: Pattern check failed")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())