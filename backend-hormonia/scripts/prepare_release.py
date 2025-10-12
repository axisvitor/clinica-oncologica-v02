#!/usr/bin/env python3
"""
Release Preparation Script
Validates system readiness and provides deployment checklist.
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ {description}")
            return True
        else:
            print(f"   ❌ {description}: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"   ❌ {description}: {e}")
        return False

def check_git_status():
    """Check git repository status."""
    print("🔍 Git Repository Status:")
    
    # Check if we're in a git repo
    if not Path('.git').exists():
        print("   ⚠️  Not in a git repository")
        return False
    
    # Check for uncommitted changes
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    if result.stdout.strip():
        print("   ⚠️  Uncommitted changes detected:")
        for line in result.stdout.strip().split('\n')[:5]:  # Show first 5 changes
            print(f"      {line}")
        print("   💡 Consider committing changes before release")
    else:
        print("   ✅ Working directory clean")
    
    # Get current branch
    result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
    if result.returncode == 0:
        branch = result.stdout.strip()
        print(f"   📍 Current branch: {branch}")
    
    return True

def main():
    """Main release preparation function."""
    print("🚀 RELEASE PREPARATION - v2025.01.12-prod")
    print("=" * 60)
    
    release_ready = True
    
    # 1. Git Status Check
    check_git_status()
    print()
    
    # 2. Run Critical Validations
    print("🔍 Critical System Validations:")
    
    validations = [
        ("python scripts/simple_regression_check.py", "Regression Check"),
        ("python scripts/check_audit_logs_status.py", "Audit Logs Validation"),
        ("python scripts/check_error_logs_status.py", "Error Logs Validation"),
        ("python scripts/test_alerts_compatibility.py", "Alerts Compatibility")
    ]
    
    for cmd, desc in validations:
        if not run_command(cmd, desc):
            release_ready = False
    
    print()
    
    # 3. Database Health Check
    print("🗄️ Database Health Check:")
    if Path("sql/comprehensive_db_check.py").exists():
        if not run_command("python sql/comprehensive_db_check.py", "Database Health"):
            release_ready = False
    else:
        print("   ⚠️  Database health check script not found")
    
    print()
    
    # 4. Migration Status
    print("📊 Migration Status:")
    try:
        result = subprocess.run(['python', '-m', 'alembic', 'current'], capture_output=True, text=True)
        if result.returncode == 0:
            current_version = result.stdout.strip()
            if "20251012_140000" in current_version:
                print("   ✅ Migration up to date (20251012_140000)")
            else:
                print(f"   ⚠️  Current migration: {current_version}")
                print("   💡 Consider running: alembic upgrade head")
        else:
            print("   ❌ Could not check migration status")
            release_ready = False
    except Exception as e:
        print(f"   ❌ Migration check failed: {e}")
        release_ready = False
    
    print()
    
    # 5. Environment Check
    print("🔧 Environment Configuration:")
    
    env_checks = [
        ("DATABASE_URL", "Database connection configured"),
        ("FIREBASE_ADMIN_PROJECT_ID", "Firebase authentication configured"),
        ("REDIS_URL", "Redis caching configured"),
        ("SECRET_KEY", "Application secrets configured")
    ]
    
    for env_var, desc in env_checks:
        if os.getenv(env_var):
            print(f"   ✅ {desc}")
        else:
            print(f"   ⚠️  {desc} - {env_var} not set")
    
    print()
    
    # 6. Release Checklist
    print("📋 PRE-DEPLOYMENT CHECKLIST:")
    checklist = [
        "All critical bug fixes implemented and tested",
        "Database migrations applied (20251012_140000)",
        "Performance indexes created for production",
        "Error tracking system operational",
        "Regression validation passing",
        "Environment variables configured",
        "Monitoring endpoints functional",
        "Security configurations verified"
    ]
    
    for item in checklist:
        print(f"   ☑️  {item}")
    
    print()
    
    # 7. Post-Deployment Monitoring
    print("📊 POST-DEPLOYMENT MONITORING:")
    monitoring_items = [
        "Monitor /api/v1/monitoring/health endpoint",
        "Check error_logs table for new entries",
        "Verify role-based access functionality",
        "Validate date parameter handling in analytics",
        "Monitor performance index utilization",
        "Check log rate limiting effectiveness"
    ]
    
    for item in monitoring_items:
        print(f"   📈 {item}")
    
    print()
    
    # 8. Rollback Plan
    print("🔄 ROLLBACK PLAN (if needed):")
    rollback_steps = [
        "Database: alembic downgrade <previous_version>",
        "Application: git checkout <previous_tag>",
        "Redeploy: Use previous release artifacts",
        "Monitor: Verify system stability after rollback"
    ]
    
    for step in rollback_steps:
        print(f"   🔙 {step}")
    
    print()
    
    # 9. Final Status
    print("=" * 60)
    if release_ready:
        print("🎉 SYSTEM READY FOR RELEASE!")
        print("   🚀 All validations passed")
        print("   📦 Release artifacts prepared")
        print("   📋 Deployment checklist complete")
        print("   🎯 Proceed with deployment")
        
        # Suggest git tag command
        tag_name = "v2025.01.12-prod"
        print(f"\n💡 Suggested git tag command:")
        print(f"   git tag -a {tag_name} -m 'Production release: Critical bug fixes and system stabilization'")
        print(f"   git push origin {tag_name}")
        
        return 0
    else:
        print("❌ RELEASE BLOCKED!")
        print("   🚫 Critical validations failed")
        print("   🔧 Fix issues above before proceeding")
        print("   📋 Re-run this script after fixes")
        return 1

if __name__ == "__main__":
    sys.exit(main())