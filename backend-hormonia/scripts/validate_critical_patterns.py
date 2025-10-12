#!/usr/bin/env python3
"""
Pre-commit validation script for critical bug patterns.
Validates dependency injection patterns, role enum usage, database model compatibility,
and date parameter handling to prevent regression of critical bugs.
"""

import ast
import os
import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
import importlib.util
import traceback


class CriticalPatternValidator:
    """Validates critical patterns to prevent regression of fixed bugs."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.backend_root = Path(__file__).parent.parent
        
    def validate_all(self) -> bool:
        """Run all validation checks."""
        print("🔍 Running critical pattern validation...")
        
        success = True
        success &= self.validate_dependency_injection_patterns()
        success &= self.validate_role_enum_usage()
        success &= self.validate_database_model_compatibility()
        success &= self.validate_date_parameter_handling()
        
        self._print_results()
        return success
    
    def validate_dependency_injection_patterns(self) -> bool:
        """Validate dependency injection patterns to prevent generator issues."""
        print("  📦 Checking dependency injection patterns...")
        
        di_files = [
            "app/dependencies/service_dependencies.py",
            "app/dependencies/__init__.py"
        ]
        
        success = True
        for file_path in di_files:
            full_path = self.backend_root / file_path
            if not full_path.exists():
                continue
                
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for proper yield from usage in DI classes
                if "_ThreadSafeProviderDependency" in content:
                    if "return get_thread_safe_service_provider()" in content:
                        self.errors.append(
                            f"❌ {file_path}: Found 'return' instead of 'yield from' in DI class"
                        )
                        success = False
                    elif "yield from get_thread_safe_service_provider()" not in content:
                        self.warnings.append(
                            f"⚠️ {file_path}: Could not verify 'yield from' pattern in DI class"
                        )
                
                # Check for generator object returns in __call__ methods
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.FunctionDef) and 
                        node.name == "__call__" and
                        any(isinstance(stmt, ast.Return) for stmt in node.body)):
                        
                        for stmt in node.body:
                            if (isinstance(stmt, ast.Return) and 
                                stmt.value and
                                isinstance(stmt.value, ast.Call)):
                                self.warnings.append(
                                    f"⚠️ {file_path}:{node.lineno}: __call__ method returns function call - verify it's not a generator"
                                )
                
            except Exception as e:
                self.errors.append(f"❌ Error parsing {file_path}: {e}")
                success = False
        
        return success
    
    def validate_role_enum_usage(self) -> bool:
        """Validate role enum usage to prevent non-existent role references."""
        print("  👤 Checking role enum usage...")
        
        # First, find the UserRole enum definition
        user_model_path = self.backend_root / "app/models/user.py"
        valid_roles = set()
        
        if user_model_path.exists():
            try:
                with open(user_model_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract enum values
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.ClassDef) and 
                        node.name == "UserRole" and
                        any(isinstance(base, ast.Name) and base.id == "Enum" 
                            for base in node.bases)):
                        
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        valid_roles.add(target.id)
                
            except Exception as e:
                self.errors.append(f"❌ Error parsing user model: {e}")
                return False
        
        if not valid_roles:
            self.warnings.append("⚠️ Could not find UserRole enum definition")
            return True
        
        print(f"    Found valid roles: {', '.join(sorted(valid_roles))}")
        
        # Check API files for role usage
        api_files = list((self.backend_root / "app/api").rglob("*.py"))
        success = True
        
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for UserRole references
                if "UserRole." in content:
                    # Find all UserRole.SOMETHING patterns
                    role_pattern = r'UserRole\.([A-Z_]+)'
                    matches = re.findall(role_pattern, content)
                    
                    for role in matches:
                        if role not in valid_roles:
                            self.errors.append(
                                f"❌ {file_path.relative_to(self.backend_root)}: "
                                f"References non-existent role UserRole.{role}"
                            )
                            success = False
                
                # Check for string role comparisons (should use enum)
                string_role_patterns = [
                    r'\.role\s*==\s*["\']([^"\']+)["\']',
                    r'["\']([^"\']+)["\']\s*==\s*.*\.role'
                ]
                
                for pattern in string_role_patterns:
                    matches = re.findall(pattern, content)
                    for role_str in matches:
                        if role_str.upper() in valid_roles:
                            self.warnings.append(
                                f"⚠️ {file_path.relative_to(self.backend_root)}: "
                                f"String comparison '{role_str}' should use UserRole.{role_str.upper()}"
                            )
                
            except Exception as e:
                self.errors.append(f"❌ Error checking {file_path}: {e}")
                success = False
        
        return success
    
    def validate_database_model_compatibility(self) -> bool:
        """Validate database models are compatible with actual schema."""
        print("  🗄️ Checking database model compatibility...")
        
        # Load schema information if available
        schema_file = self.backend_root / "sql/SCHEMA_MASTER_COMPLETO.sql"
        db_tables = {}
        
        if schema_file.exists():
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_content = f.read()
                
                # Extract table definitions (simplified)
                table_pattern = r'CREATE TABLE\s+(\w+)\s*\((.*?)\);'
                matches = re.findall(table_pattern, schema_content, re.DOTALL | re.IGNORECASE)
                
                for table_name, columns_def in matches:
                    columns = []
                    for line in columns_def.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('--'):
                            # Extract column name (first word)
                            col_match = re.match(r'(\w+)', line)
                            if col_match:
                                columns.append(col_match.group(1).lower())
                    
                    db_tables[table_name.lower()] = columns
                
            except Exception as e:
                self.warnings.append(f"⚠️ Could not parse schema file: {e}")
        
        # Check model files
        model_files = list((self.backend_root / "app/models").glob("*.py"))
        success = True
        
        for file_path in model_files:
            if file_path.name == "__init__.py":
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for SQLAlchemy models
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.ClassDef) and
                        any(isinstance(base, ast.Name) and base.id == "Base" 
                            for base in node.bases)):
                        
                        # Find __tablename__
                        table_name = None
                        for item in node.body:
                            if (isinstance(item, ast.Assign) and
                                any(isinstance(target, ast.Name) and target.id == "__tablename__"
                                    for target in item.targets)):
                                if isinstance(item.value, ast.Constant):
                                    table_name = item.value.value
                        
                        if table_name and table_name.lower() in db_tables:
                            # Check column mappings
                            model_columns = []
                            for item in node.body:
                                if isinstance(item, ast.Assign):
                                    for target in item.targets:
                                        if isinstance(target, ast.Name):
                                            # Check if it's a Column definition
                                            if (isinstance(item.value, ast.Call) and
                                                isinstance(item.value.func, ast.Name) and
                                                item.value.func.id == "Column"):
                                                
                                                # Check for column name mapping
                                                actual_col_name = target.id
                                                if item.value.args and isinstance(item.value.args[0], ast.Constant):
                                                    actual_col_name = item.value.args[0].value
                                                
                                                model_columns.append(actual_col_name.lower())
                            
                            # Compare with schema
                            schema_columns = set(db_tables[table_name.lower()])
                            model_column_set = set(model_columns)
                            
                            missing_in_schema = model_column_set - schema_columns
                            if missing_in_schema:
                                self.warnings.append(
                                    f"⚠️ {file_path.relative_to(self.backend_root)}: "
                                    f"Model {node.name} references columns not in schema: {missing_in_schema}"
                                )
                
            except Exception as e:
                self.errors.append(f"❌ Error checking model {file_path}: {e}")
                success = False
        
        return success
    
    def validate_date_parameter_handling(self) -> bool:
        """Validate date parameter handling in API endpoints."""
        print("  📅 Checking date parameter handling...")
        
        api_files = list((self.backend_root / "app/api").rglob("*.py"))
        success = True
        
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for date parameters in function signatures
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check function parameters
                        for arg in node.args.args:
                            # Look for date-related parameter names
                            if any(date_word in arg.arg.lower() 
                                   for date_word in ['date', 'time', 'timestamp']):
                                
                                # Check if there's proper type annotation
                                if arg.annotation:
                                    annotation_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                                    
                                    # Should use Optional[str] or str for date parameters (not date)
                                    if 'date' in annotation_str and 'str' not in annotation_str:
                                        self.warnings.append(
                                            f"⚠️ {file_path.relative_to(self.backend_root)}:{node.lineno}: "
                                            f"Parameter '{arg.arg}' should accept str type for date conversion"
                                        )
                
                # Check for coerce_to_date usage
                if "coerce_to_date" in content:
                    # Good - using date coercion utility
                    pass
                elif any(date_word in content.lower() for date_word in ['start_date', 'end_date']):
                    # Check if date parameters are handled properly
                    if "HTTPException" not in content:
                        self.warnings.append(
                            f"⚠️ {file_path.relative_to(self.backend_root)}: "
                            f"Date parameters found but no error handling visible"
                        )
                
            except Exception as e:
                self.errors.append(f"❌ Error checking {file_path}: {e}")
                success = False
        
        return success
    
    def _print_results(self):
        """Print validation results."""
        if self.errors:
            print("\n❌ Critical Issues Found:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️ Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("✅ All critical pattern validations passed!")
        elif not self.errors:
            print("✅ No critical issues found (warnings only)")


def main():
    """Main entry point for pre-commit hook."""
    validator = CriticalPatternValidator()
    success = validator.validate_all()
    
    if not success:
        print("\n💥 Critical pattern validation failed!")
        sys.exit(1)
    else:
        print("\n🎉 Critical pattern validation passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()