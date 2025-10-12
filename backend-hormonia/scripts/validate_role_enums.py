#!/usr/bin/env python3
"""
Role Enum Usage Validator
Ensures consistent role enum usage and prevents references to non-existent roles.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Set, List, Dict


class RoleEnumValidator:
    """Validates role enum usage consistency."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.backend_root = Path(__file__).parent.parent
        self.valid_roles: Set[str] = set()
    
    def validate(self) -> bool:
        """Validate all role enum usage."""
        print("🔍 Validating role enum usage...")
        
        success = True
        success &= self.discover_valid_roles()
        success &= self.check_role_references()
        success &= self.check_string_comparisons()
        success &= self.check_permission_decorators()
        
        self._print_results()
        return success and not self.errors
    
    def discover_valid_roles(self) -> bool:
        """Discover valid roles from UserRole enum."""
        user_model_path = self.backend_root / "app/models/user.py"
        
        if not user_model_path.exists():
            self.errors.append("❌ app/models/user.py not found")
            return False
        
        try:
            with open(user_model_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if (isinstance(node, ast.ClassDef) and 
                    node.name == "UserRole"):
                    
                    # Check if it's an Enum
                    is_enum = any(
                        (isinstance(base, ast.Name) and base.id == "Enum") or
                        (isinstance(base, ast.Attribute) and base.attr == "Enum")
                        for base in node.bases
                    )
                    
                    if is_enum:
                        # Extract enum values
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        self.valid_roles.add(target.id)
            
            if not self.valid_roles:
                self.errors.append("❌ No UserRole enum found or no roles defined")
                return False
            
            print(f"  📋 Found valid roles: {', '.join(sorted(self.valid_roles))}")
            return True
        
        except Exception as e:
            self.errors.append(f"❌ Error parsing user model: {e}")
            return False
    
    def check_role_references(self) -> bool:
        """Check for references to non-existent roles."""
        python_files = list((self.backend_root / "app").rglob("*.py"))
        success = True
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find UserRole.SOMETHING patterns
                role_pattern = r'UserRole\.([A-Z_]+)'
                matches = re.finditer(role_pattern, content)
                
                for match in matches:
                    role = match.group(1)
                    if role not in self.valid_roles:
                        line_num = content[:match.start()].count('\n') + 1
                        self.errors.append(
                            f"❌ {file_path.relative_to(self.backend_root)}:{line_num}: "
                            f"References non-existent role UserRole.{role}"
                        )
                        success = False
                
                # Check for set/list definitions with roles
                set_pattern = r'\{[^}]*UserRole\.[A-Z_]+[^}]*\}'
                set_matches = re.finditer(set_pattern, content)
                
                for match in set_matches:
                    set_content = match.group(0)
                    roles_in_set = re.findall(r'UserRole\.([A-Z_]+)', set_content)
                    
                    for role in roles_in_set:
                        if role not in self.valid_roles:
                            line_num = content[:match.start()].count('\n') + 1
                            self.errors.append(
                                f"❌ {file_path.relative_to(self.backend_root)}:{line_num}: "
                                f"Set contains non-existent role UserRole.{role}"
                            )
                            success = False
            
            except Exception as e:
                self.errors.append(f"❌ Error checking {file_path}: {e}")
                success = False
        
        return success
    
    def check_string_comparisons(self) -> bool:
        """Check for string-based role comparisons that should use enums."""
        python_files = list((self.backend_root / "app").rglob("*.py"))
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Pattern for role string comparisons
                patterns = [
                    r'\.role\s*==\s*["\']([^"\']+)["\']',
                    r'["\']([^"\']+)["\']\s*==\s*[^"\']*\.role',
                    r'\.role\s*!=\s*["\']([^"\']+)["\']',
                    r'["\']([^"\']+)["\']\s*!=\s*[^"\']*\.role'
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        role_str = match.group(1)
                        role_upper = role_str.upper()
                        
                        if role_upper in self.valid_roles:
                            line_num = content[:match.start()].count('\n') + 1
                            self.warnings.append(
                                f"⚠️ {file_path.relative_to(self.backend_root)}:{line_num}: "
                                f"String comparison '{role_str}' should use UserRole.{role_upper}"
                            )
                        elif role_str.lower() in [r.lower() for r in self.valid_roles]:
                            # Case mismatch
                            correct_role = next(r for r in self.valid_roles if r.lower() == role_str.lower())
                            line_num = content[:match.start()].count('\n') + 1
                            self.warnings.append(
                                f"⚠️ {file_path.relative_to(self.backend_root)}:{line_num}: "
                                f"String comparison '{role_str}' should use UserRole.{correct_role}"
                            )
            
            except Exception as e:
                self.errors.append(f"❌ Error checking {file_path}: {e}")
                return False
        
        return True
    
    def check_permission_decorators(self) -> bool:
        """Check permission decorators use valid roles."""
        python_files = list((self.backend_root / "app").rglob("*.py"))
        
        for file_path in python_files:
            if "test" in str(file_path) or "__pycache__" in str(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Check decorators
                        for decorator in node.decorator_list:
                            if (isinstance(decorator, ast.Call) and
                                isinstance(decorator.func, ast.Name)):
                                
                                # Check for permission-related decorators
                                if any(perm_word in decorator.func.id.lower() 
                                       for perm_word in ['require', 'permission', 'role']):
                                    
                                    # Check arguments for role references
                                    for arg in decorator.args:
                                        if (isinstance(arg, ast.Attribute) and
                                            isinstance(arg.value, ast.Name) and
                                            arg.value.id == "UserRole"):
                                            
                                            if arg.attr not in self.valid_roles:
                                                self.errors.append(
                                                    f"❌ {file_path.relative_to(self.backend_root)}:{node.lineno}: "
                                                    f"Decorator uses non-existent role UserRole.{arg.attr}"
                                                )
                                                return False
            
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        return True
    
    def _print_results(self):
        """Print validation results."""
        if self.errors:
            print("\n❌ Role Enum Issues:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️ Role Enum Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("✅ All role enum usage is valid!")
        elif not self.errors:
            print("✅ No critical role enum issues (warnings only)")


def main():
    """Main entry point."""
    validator = RoleEnumValidator()
    success = validator.validate()
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()