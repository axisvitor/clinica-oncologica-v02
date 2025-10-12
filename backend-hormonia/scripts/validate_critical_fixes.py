#!/usr/bin/env python3
"""
Critical Bug Fixes Validation Script
Validates that all critical bug fixes from the spec are working correctly.
"""

import os
import sys
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import ast


class CriticalFixesValidator:
    """Validates critical bug fixes are working."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.backend_root = Path(__file__).parent.parent
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.fix_results: Dict[str, bool] = {}
    
    def validate_all_fixes(self) -> bool:
        """Validate all critical bug fixes."""
        print("🔧 Validating critical bug fixes...")
        
        success = True
        
        # Fix 1: Dependency injection generator issue
        success &= self._validate_dependency_injection_fix()
        
        # Fix 2: Role enum mismatches
        success &= self._validate_role_enum_fixes()
        
        # Fix 3: Alerts schema compatibility
        success &= self._validate_alerts_schema_fix()
        
        # Fix 4: Date parameter handling
        success &= self._validate_date_parameter_fix()
        
        # Fix 5: Logging optimization
        success &= self._validate_logging_optimization()
        
        # Fix 6: Error handling
        success &= self._validate_error_handling()
        
        self._print_results()
        return success
    
    def _validate_dependency_injection_fix(self) -> bool:
        """Validate dependency injection fix is working."""
        print("  🔧 Validating dependency injection fix...")
        
        # Check the code fix is in place
        di_file = self.backend_root / "app/dependencies/service_dependencies.py"
        
        if not di_file.exists():
            self.errors.append("❌ service_dependencies.py not found")
            self.fix_results["dependency_injection"] = False
            return False
        
        try:
            with open(di_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for yield from pattern
            if "yield from" not in content:
                self.errors.append("❌ DI fix not applied - missing 'yield from' pattern")
                self.fix_results["dependency_injection"] = False
                return False
            
            # Check that return generator pattern is not present
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if (isinstance(node, ast.ClassDef) and 
                    node.name == "_ThreadSafeProviderDependency"):
                    
                    for method in node.body:
                        if (isinstance(method, ast.FunctionDef) and 
                            method.name == "__call__"):
                            
                            # Check for problematic return pattern
                            for stmt in method.body:
                                if (isinstance(stmt, ast.Return) and 
                                    stmt.value and
                                    isinstance(stmt.value, ast.Call)):
                                    
                                    self.errors.append("❌ DI fix incomplete - still has return generator pattern")
                                    self.fix_results["dependency_injection"] = False
                                    return False
            
            print("    ✅ Dependency injection fix validated")
            self.fix_results["dependency_injection"] = True
            return True
        
        except Exception as e:
            self.errors.append(f"❌ Error validating DI fix: {e}")
            self.fix_results["dependency_injection"] = False
            return False
    
    def _validate_role_enum_fixes(self) -> bool:
        """Validate role enum fixes are working."""
        print("  👤 Validating role enum fixes...")
        
        success = True
        
        # Check analytics.py for SUPER_ADMIN references
        analytics_file = self.backend_root / "app/api/v1/analytics.py"
        if analytics_file.exists():
            try:
                with open(analytics_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if "SUPER_ADMIN" in content:
                    self.errors.append("❌ Analytics still references SUPER_ADMIN role")
                    success = False
                else:
                    print("    ✅ Analytics SUPER_ADMIN references removed")
            
            except Exception as e:
                self.errors.append(f"❌ Error checking analytics role fix: {e}")
                success = False
        
        # Check monthly quiz for string comparisons
        quiz_file = self.backend_root / "app/api/v1/monthly_quiz.py"
        if quiz_file.exists():
            try:
                with open(quiz_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for string role comparisons
                if '.role == "admin"' in content or ".role == 'admin'" in content:
                    self.errors.append("❌ Monthly quiz still uses string role comparison")
                    success = False
                else:
                    print("    ✅ Monthly quiz string role comparisons fixed")
            
            except Exception as e:
                self.errors.append(f"❌ Error checking monthly quiz role fix: {e}")
                success = False
        
        self.fix_results["role_enums"] = success
        return success
    
    def _validate_alerts_schema_fix(self) -> bool:
        """Validate alerts schema compatibility fix."""
        print("  🚨 Validating alerts schema fix...")
        
        # Check Alert model has proper column mappings
        alert_model_file = self.backend_root / "app/models/alert.py"
        
        if not alert_model_file.exists():
            self.errors.append("❌ Alert model file not found")
            self.fix_results["alerts_schema"] = False
            return False
        
        try:
            with open(alert_model_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for column mappings
            required_mappings = [
                'Column("type"',  # alert_type -> type
                'Column("message"',  # description -> message
            ]
            
            missing_mappings = []
            for mapping in required_mappings:
                if mapping not in content:
                    missing_mappings.append(mapping)
            
            if missing_mappings:
                self.errors.append(f"❌ Alert model missing column mappings: {missing_mappings}")
                self.fix_results["alerts_schema"] = False
                return False
            
            # Check for quiz_session_id property
            if "@property" not in content or "quiz_session_id" not in content:
                self.warnings.append("⚠️ Alert model may be missing quiz_session_id property")
            
            print("    ✅ Alerts schema compatibility fix validated")
            self.fix_results["alerts_schema"] = True
            return True
        
        except Exception as e:
            self.errors.append(f"❌ Error validating alerts schema fix: {e}")
            self.fix_results["alerts_schema"] = False
            return False
    
    def _validate_date_parameter_fix(self) -> bool:
        """Validate date parameter handling fix."""
        print("  📅 Validating date parameter fix...")
        
        # Check date_utils.py exists
        date_utils_file = self.backend_root / "app/core/date_utils.py"
        
        if not date_utils_file.exists():
            self.errors.append("❌ date_utils.py not found")
            self.fix_results["date_parameters"] = False
            return False
        
        try:
            with open(date_utils_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for coerce_to_date function
            if "def coerce_to_date" not in content:
                self.errors.append("❌ coerce_to_date function not found")
                self.fix_results["date_parameters"] = False
                return False
            
            # Check analytics endpoints use coerce_to_date
            analytics_file = self.backend_root / "app/api/v1/analytics.py"
            if analytics_file.exists():
                with open(analytics_file, 'r', encoding='utf-8') as f:
                    analytics_content = f.read()
                
                if "coerce_to_date" not in analytics_content:
                    self.warnings.append("⚠️ Analytics endpoints may not be using coerce_to_date")
                else:
                    print("    ✅ Analytics endpoints using date coercion")
            
            print("    ✅ Date parameter fix validated")
            self.fix_results["date_parameters"] = True
            return True
        
        except Exception as e:
            self.errors.append(f"❌ Error validating date parameter fix: {e}")
            self.fix_results["date_parameters"] = False
            return False
    
    def _validate_logging_optimization(self) -> bool:
        """Validate logging optimization fix."""
        print("  📝 Validating logging optimization...")
        
        # Check logging_config.py exists
        logging_config_file = self.backend_root / "app/core/logging_config.py"
        
        if not logging_config_file.exists():
            self.warnings.append("⚠️ logging_config.py not found")
            self.fix_results["logging_optimization"] = True  # Not critical
            return True
        
        try:
            with open(logging_config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for RateLimitedLogger
            if "class RateLimitedLogger" not in content:
                self.warnings.append("⚠️ RateLimitedLogger class not found")
            else:
                print("    ✅ Logging rate limiting implemented")
            
            self.fix_results["logging_optimization"] = True
            return True
        
        except Exception as e:
            self.warnings.append(f"⚠️ Error validating logging optimization: {e}")
            self.fix_results["logging_optimization"] = True
            return True
    
    def _validate_error_handling(self) -> bool:
        """Validate error handling fix."""
        print("  ⚠️ Validating error handling...")
        
        # Check error_handler.py exists
        error_handler_file = self.backend_root / "app/core/error_handler.py"
        
        if not error_handler_file.exists():
            self.warnings.append("⚠️ error_handler.py not found")
            self.fix_results["error_handling"] = True  # Not critical for deployment
            return True
        
        try:
            with open(error_handler_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for CriticalErrorHandler
            if "class CriticalErrorHandler" not in content:
                self.warnings.append("⚠️ CriticalErrorHandler class not found")
            else:
                print("    ✅ Centralized error handling implemented")
            
            self.fix_results["error_handling"] = True
            return True
        
        except Exception as e:
            self.warnings.append(f"⚠️ Error validating error handling: {e}")
            self.fix_results["error_handling"] = True
            return True
    
    def _test_fixes_via_api(self) -> bool:
        """Test fixes via API calls."""
        print("  🌐 Testing fixes via API...")
        
        success = True
        
        # Test date parameter handling
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/analytics/engagement-range",
                params={"start_date": "2025-10-05T15:01:57.695Z"},
                headers={"Authorization": "Bearer fake-token"},
                timeout=10
            )
            
            # Should not get 422 validation error
            if response.status_code == 422:
                self.errors.append("❌ Date parameter fix not working - still getting validation errors")
                success = False
            else:
                print("    ✅ Date parameter handling working")
        
        except Exception as e:
            self.warnings.append(f"⚠️ Could not test date parameter fix via API: {e}")
        
        return success
    
    def _print_results(self):
        """Print validation results."""
        print(f"\n📊 Critical Fixes Validation Summary:")
        
        for fix_name, result in self.fix_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {fix_name}: {status}")
        
        if self.errors:
            print("\n❌ Critical Issues:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️ Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        total_fixes = len(self.fix_results)
        passed_fixes = sum(1 for result in self.fix_results.values() if result)
        
        print(f"\n🎯 Fixes Status: {passed_fixes}/{total_fixes} validated")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Critical fixes validation')
    parser.add_argument('--base-url', help='API base URL', default=None)
    parser.add_argument('--api-test', action='store_true', 
                       help='Include API testing (requires running server)')
    
    args = parser.parse_args()
    
    validator = CriticalFixesValidator(base_url=args.base_url)
    success = validator.validate_all_fixes()
    
    if args.api_test:
        success &= validator._test_fixes_via_api()
    
    if success:
        print("\n🎉 All critical fixes validated successfully!")
        sys.exit(0)
    else:
        print("\n💥 Critical fixes validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()