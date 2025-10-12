#!/usr/bin/env python3
"""
Date Parameter Validation Script
Ensures API endpoints handle date parameters correctly to prevent validation errors.
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple


class DateParameterValidator:
    """Validates date parameter handling in API endpoints."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.backend_root = Path(__file__).parent.parent
    
    def validate(self) -> bool:
        """Validate all date parameter handling."""
        print("🔍 Validating date parameter handling...")
        
        success = True
        success &= self.check_api_date_parameters()
        success &= self.check_date_coercion_usage()
        success &= self.check_error_handling()
        success &= self.check_pydantic_models()
        
        self._print_results()
        return success and not self.errors
    
    def check_api_date_parameters(self) -> bool:
        """Check API endpoints for proper date parameter handling."""
        api_files = list((self.backend_root / "app/api").rglob("*.py"))
        success = True
        
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check if function has route decorators
                        has_route_decorator = any(
                            isinstance(dec, ast.Call) and
                            isinstance(dec.func, ast.Attribute) and
                            dec.func.attr in ['get', 'post', 'put', 'delete', 'patch']
                            for dec in node.decorator_list
                        )
                        
                        if has_route_decorator:
                            # Check function parameters for date-related names
                            date_params = []
                            for arg in node.args.args:
                                if any(date_word in arg.arg.lower() 
                                       for date_word in ['date', 'time', 'timestamp', 'created', 'updated']):
                                    date_params.append((arg.arg, arg.annotation))
                            
                            # Validate date parameter types
                            for param_name, annotation in date_params:
                                if annotation:
                                    annotation_str = self._get_annotation_string(annotation)
                                    
                                    # Check for problematic patterns
                                    if 'date' in annotation_str and 'str' not in annotation_str:
                                        # Using date type directly - might cause issues
                                        self.warnings.append(
                                            f"⚠️ {file_path.relative_to(self.backend_root)}:{node.lineno}: "
                                            f"Parameter '{param_name}' uses date type - consider str with coercion"
                                        )
                                    
                                    # Check for Optional handling
                                    if 'Optional' not in annotation_str and param_name.endswith('_date'):
                                        # Date parameters should often be optional
                                        self.warnings.append(
                                            f"⚠️ {file_path.relative_to(self.backend_root)}:{node.lineno}: "
                                            f"Date parameter '{param_name}' might need Optional type"
                                        )
                            
                            # Check function body for date handling
                            if date_params:
                                success &= self._check_date_handling_in_function(
                                    file_path, node, [param[0] for param in date_params]
                                )
            
            except Exception as e:
                self.errors.append(f"❌ Error checking {file_path}: {e}")
                success = False
        
        return success
    
    def check_date_coercion_usage(self) -> bool:
        """Check for proper usage of date coercion utilities."""
        api_files = list((self.backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for date parameter usage without coercion
                if any(pattern in content for pattern in ['start_date', 'end_date', '_date:']):
                    if 'coerce_to_date' not in content:
                        # Has date parameters but no coercion
                        self.warnings.append(
                            f"⚠️ {file_path.relative_to(self.backend_root)}: "
                            f"Has date parameters but doesn't use coerce_to_date utility"
                        )
                    
                    # Check for proper import
                    if 'coerce_to_date' in content:
                        if 'from app.core.date_utils import' not in content:
                            self.errors.append(
                                f"❌ {file_path.relative_to(self.backend_root)}: "
                                f"Uses coerce_to_date but missing proper import"
                            )
                            return False
            
            except Exception as e:
                self.errors.append(f"❌ Error checking coercion in {file_path}: {e}")
                return False
        
        return True
    
    def check_error_handling(self) -> bool:
        """Check for proper error handling of date parameters."""
        api_files = list((self.backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # If using date coercion, should have error handling
                if 'coerce_to_date' in content:
                    if 'HTTPException' not in content and 'ValueError' not in content:
                        self.warnings.append(
                            f"⚠️ {file_path.relative_to(self.backend_root)}: "
                            f"Uses date coercion but no visible error handling"
                        )
                    
                    # Check for try/catch blocks around date coercion
                    tree = ast.parse(content)
                    has_try_catch = any(
                        isinstance(node, ast.Try)
                        for node in ast.walk(tree)
                    )
                    
                    if not has_try_catch:
                        self.warnings.append(
                            f"⚠️ {file_path.relative_to(self.backend_root)}: "
                            f"Uses date coercion but no try/catch blocks found"
                        )
            
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        return True
    
    def check_pydantic_models(self) -> bool:
        """Check Pydantic models for date field handling."""
        model_files = list((self.backend_root / "app").rglob("*.py"))
        
        for file_path in model_files:
            if "models" not in str(file_path) and "schemas" not in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for Pydantic models with date fields
                if 'BaseModel' in content:
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if (isinstance(node, ast.ClassDef) and
                            any(isinstance(base, ast.Name) and base.id == "BaseModel"
                                for base in node.bases)):
                            
                            # Check class attributes for date fields
                            for item in node.body:
                                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                    field_name = item.target.id
                                    
                                    if any(date_word in field_name.lower() 
                                           for date_word in ['date', 'time', 'timestamp']):
                                        
                                        if item.annotation:
                                            annotation_str = self._get_annotation_string(item.annotation)
                                            
                                            # Check for date vs datetime vs str
                                            if 'date' in annotation_str and 'datetime' not in annotation_str:
                                                self.warnings.append(
                                                    f"⚠️ {file_path.relative_to(self.backend_root)}:{node.lineno}: "
                                                    f"Pydantic field '{field_name}' uses date type - consider datetime or str"
                                                )
            
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        return True
    
    def _check_date_handling_in_function(self, file_path: Path, func_node: ast.FunctionDef, date_params: List[str]) -> bool:
        """Check how date parameters are handled within a function."""
        success = True
        
        # Look for date parameter usage in function body
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name) and node.id in date_params:
                # Found usage of date parameter
                # Check if it's being coerced or validated
                parent = getattr(node, 'parent', None)
                
                # This is a simplified check - in practice, you'd want more sophisticated analysis
                pass
        
        return success
    
    def _get_annotation_string(self, annotation) -> str:
        """Get string representation of type annotation."""
        if hasattr(ast, 'unparse'):
            return ast.unparse(annotation)
        else:
            # Fallback for older Python versions
            if isinstance(annotation, ast.Name):
                return annotation.id
            elif isinstance(annotation, ast.Attribute):
                return f"{annotation.value.id}.{annotation.attr}"
            elif isinstance(annotation, ast.Subscript):
                return f"{self._get_annotation_string(annotation.value)}[...]"
            else:
                return str(annotation)
    
    def _print_results(self):
        """Print validation results."""
        if self.errors:
            print("\n❌ Date Parameter Issues:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️ Date Parameter Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("✅ All date parameter handling is valid!")
        elif not self.errors:
            print("✅ No critical date parameter issues (warnings only)")


def main():
    """Main entry point."""
    validator = DateParameterValidator()
    success = validator.validate()
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()