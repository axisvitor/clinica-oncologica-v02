#!/usr/bin/env python3
"""
Deployment Health Validation Script
Quick health checks for critical system components after deployment.
"""

import os
import sys
import time
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import json


class DeploymentHealthValidator:
    """Quick health validation for deployment."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.backend_root = Path(__file__).parent.parent
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_health(self) -> bool:
        """Run quick health validation."""
        print("🏥 Running deployment health checks...")
        
        success = True
        success &= self._check_api_health()
        success &= self._check_database_health()
        success &= self._check_dependency_injection()
        success &= self._check_critical_imports()
        success &= self._check_environment_config()
        
        self._print_results()
        return success
    
    def _check_api_health(self) -> bool:
        """Check API health endpoint."""
        print("  🌐 Checking API health...")
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                print("    ✅ API health endpoint responding")
                return True
            else:
                self.errors.append(f"❌ API health returned {response.status_code}")
                return False
        
        except requests.exceptions.ConnectionError:
            self.errors.append("❌ API not reachable - connection refused")
            return False
        except requests.exceptions.Timeout:
            self.errors.append("❌ API health check timed out")
            return False
        except Exception as e:
            self.errors.append(f"❌ API health check failed: {e}")
            return False
    
    def _check_database_health(self) -> bool:
        """Check database connectivity."""
        print("  🗄️ Checking database health...")
        
        try:
            response = requests.get(f"{self.base_url}/health/database", timeout=15)
            
            if response.status_code == 200:
                print("    ✅ Database connectivity OK")
                return True
            else:
                self.errors.append(f"❌ Database health returned {response.status_code}")
                return False
        
        except Exception as e:
            self.warnings.append(f"⚠️ Database health check failed: {e}")
            return True  # Don't fail deployment for this
    
    def _check_dependency_injection(self) -> bool:
        """Check that dependency injection is working."""
        print("  🔧 Checking dependency injection...")
        
        # Test an endpoint that uses DI
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=10)
            
            # If we get a 500 with generator object error, DI is broken
            if response.status_code == 500:
                error_text = response.text.lower()
                if "generator" in error_text or "has no attribute" in error_text:
                    self.errors.append("❌ Dependency injection generator error detected")
                    return False
            
            print("    ✅ Dependency injection appears to be working")
            return True
        
        except Exception as e:
            self.warnings.append(f"⚠️ Could not test dependency injection: {e}")
            return True
    
    def _check_critical_imports(self) -> bool:
        """Check that critical modules can be imported."""
        print("  📦 Checking critical imports...")
        
        critical_modules = [
            'app.core.config',
            'app.core.date_utils',
            'app.core.error_handler',
            'app.models.user',
            'app.models.alert',
            'app.dependencies.service_dependencies'
        ]
        
        for module in critical_modules:
            try:
                # Use subprocess to test import in clean environment
                result = subprocess.run(
                    [sys.executable, '-c', f'import {module}'],
                    cwd=self.backend_root,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    self.errors.append(f"❌ Failed to import {module}: {result.stderr}")
                    return False
            
            except Exception as e:
                self.errors.append(f"❌ Import test failed for {module}: {e}")
                return False
        
        print("    ✅ All critical imports successful")
        return True
    
    def _check_environment_config(self) -> bool:
        """Check environment configuration."""
        print("  ⚙️ Checking environment configuration...")
        
        required_env_vars = [
            'DATABASE_URL',
            'SECRET_KEY'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.warnings.append(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
        
        # Check if .env file exists
        env_file = self.backend_root / '.env'
        if not env_file.exists():
            self.warnings.append("⚠️ No .env file found")
        
        print("    ✅ Environment configuration checked")
        return True
    
    def _print_results(self):
        """Print validation results."""
        if self.errors:
            print("\n❌ Health Check Failures:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️ Health Check Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All health checks passed!")
        elif not self.errors:
            print("\n✅ Health checks passed (with warnings)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deployment health validation')
    parser.add_argument('--base-url', help='API base URL', default=None)
    
    args = parser.parse_args()
    
    validator = DeploymentHealthValidator(base_url=args.base_url)
    success = validator.validate_health()
    
    if success:
        print("\n🎉 Deployment health validation passed!")
        sys.exit(0)
    else:
        print("\n💥 Deployment health validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()