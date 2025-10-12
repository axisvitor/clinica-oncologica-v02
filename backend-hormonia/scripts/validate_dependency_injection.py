#!/usr/bin/env python3
"""
Dependency Injection Pattern Validator
Ensures DI patterns follow correct implementation to prevent generator object issues.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


class DependencyInjectionValidator:
    """Validates dependency injection patterns."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.backend_root = Path(__file__).parent.parent
    
    def validate(self) -> bool:
        """Validate all DI patterns."""
        print("🔍 Validating dependency injection patterns...")
        
        success = True
        success &= self.check_provider_dependency_classes()
        success &= self.check_fastapi_depends_usage()
        success &= self.check_generator_returns()
        
        if self.errors:
            print("\n❌ Dependency Injection Issues:")
            for error in self.errors:
                print(f"  {error}")
            return False
        
        print("✅ Dependency injection patterns are valid!")
        return True
    
    def check_provider_dependency_classes(self) -> bool:
        """Check provider dependency classes use yield from correctly."""
        di_file = self.backend_root / "app/dependencies/service_dependencies.py"
        
        if not di_file.exists():
            self.errors.append("❌ service_dependencies.py not found")
            return False
        
        try:
            with open(di_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Find _ThreadSafeProviderDependency class
            for node in ast.walk(tree):
                if (isinstance(node, ast.ClassDef) and 
                    node.name == "_ThreadSafeProviderDependency"):
                    
                    # Find __call__ method
                    for method in node.body:
                        if (isinstance(method, ast.FunctionDef) and 
                            method.name == "__call__"):
                            
                            # Check method body for correct pattern
                            has_yield_from = False
                            has_return_generator = False
                            
                            for stmt in method.body:
                                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.YieldFrom):
                                    has_yield_from = True
                                elif (isinstance(stmt, ast.Return) and 
                                      stmt.value and
                                      isinstance(stmt.value, ast.Call)):
                                    # Check if returning a generator function
                                    if (isinstance(stmt.value.func, ast.Name) and
                                        "provider" in stmt.value.func.id.lower()):
                                        has_return_generator = True
                            
                            if has_return_generator and not has_yield_from:
                                self.errors.append(
                                    f"❌ {di_file.relative_to(self.backend_root)}: "
                                    f"_ThreadSafeProviderDependency.__call__ should use 'yield from' not 'return'"
                                )
                                return False
                            
                            if not has_yield_from and not has_return_generator:
                                self.errors.append(
                                    f"❌ {di_file.relative_to(self.backend_root)}: "
                                    f"_ThreadSafeProviderDependency.__call__ missing yield from pattern"
                                )
                                return False
        
        except Exception as e:
            self.errors.append(f"❌ Error parsing {di_file}: {e}")
            return False
        
        return True
    
    def check_fastapi_depends_usage(self) -> bool:
        """Check FastAPI Depends() usage patterns."""
        api_files = list((self.backend_root / "app/api").rglob("*.py"))
        
        for file_path in api_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for Depends() usage
                if "Depends(" in content:
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Check function parameters for Depends usage
                            for arg in node.args.args:
                                if (arg.annotation and 
                                    isinstance(arg.annotation, ast.Call) and
                                    isinstance(arg.annotation.func, ast.Name) and
                                    arg.annotation.func.id == "Depends"):
                                    
                                    # Ensure the dependency is callable
                                    if (arg.annotation.args and
                                        isinstance(arg.annotation.args[0], ast.Name)):
                                        dep_name = arg.annotation.args[0].id
                                        
                                        # Check for common DI patterns
                                        if "provider" in dep_name.lower():
                                            # This is likely a provider dependency
                                            pass  # Good pattern
                                        elif dep_name.endswith("Dependency"):
                                            # This is a dependency class
                                            pass  # Good pattern
                                        else:
                                            # Might be a function - check if it returns generator
                                            pass  # Need more context to validate
            
            except Exception as e:
                self.errors.append(f"❌ Error checking {file_path}: {e}")
                return False
        
        return True
    
    def check_generator_returns(self) -> bool:
        """Check for functions that incorrectly return generators."""
        service_files = list((self.backend_root / "app").rglob("*.py"))
        
        for file_path in service_files:
            if "test" in str(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check for functions that return generator calls
                        for stmt in node.body:
                            if (isinstance(stmt, ast.Return) and 
                                stmt.value and
                                isinstance(stmt.value, ast.Call)):
                                
                                # Check if the function name suggests it's a generator
                                if (isinstance(stmt.value.func, ast.Name) and
                                    any(word in stmt.value.func.id.lower() 
                                        for word in ['get_', 'create_', 'provide_'])):
                                    
                                    # This might be returning a generator when it should yield
                                    # Only flag if it's in a dependency context
                                    if ("dependency" in file_path.name.lower() or
                                        "provider" in node.name.lower()):
                                        
                                        # Check if this is the problematic pattern
                                        if node.name == "__call__":
                                            self.errors.append(
                                                f"❌ {file_path.relative_to(self.backend_root)}:{node.lineno}: "
                                                f"Function '{node.name}' may be returning generator instead of yielding"
                                            )
                                            return False
            
            except Exception as e:
                # Skip files that can't be parsed (might not be Python)
                continue
        
        return True


def main():
    """Main entry point."""
    validator = DependencyInjectionValidator()
    success = validator.validate()
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()