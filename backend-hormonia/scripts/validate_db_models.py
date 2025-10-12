#!/usr/bin/env python3
"""
Database Model Compatibility Validator
Ensures database models are compatible with actual database schema.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


class DatabaseModelValidator:
    """Validates database model compatibility with schema."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.backend_root = Path(__file__).parent.parent
        self.schema_tables: Dict[str, Dict[str, str]] = {}
    
    def validate(self) -> bool:
        """Validate all database model compatibility."""
        print("🔍 Validating database model compatibility...")
        
        success = True
        success &= self.load_schema_information()
        success &= self.validate_model_tables()
        success &= self.validate_column_mappings()
        success &= self.validate_relationships()
        
        self._print_results()
        return success and not self.errors
    
    def load_schema_information(self) -> bool:
        """Load database schema information."""
        schema_files = [
            "sql/SCHEMA_MASTER_COMPLETO.sql",
            "sql/schema.sql",
            "alembic/versions/*.py"
        ]
        
        # Try to load from SQL schema file
        for schema_pattern in schema_files:
            if "*" in schema_pattern:
                # Handle glob patterns
                schema_dir = self.backend_root / Path(schema_pattern).parent
                if schema_dir.exists():
                    for schema_file in schema_dir.glob(Path(schema_pattern).name):
                        if self._load_schema_file(schema_file):
                            break
            else:
                schema_file = self.backend_root / schema_pattern
                if schema_file.exists():
                    if self._load_schema_file(schema_file):
                        break
        
        if not self.schema_tables:
            self.warnings.append("⚠️ No database schema information found - skipping schema validation")
            return True
        
        print(f"  📊 Loaded schema for {len(self.schema_tables)} tables")
        return True
    
    def _load_schema_file(self, schema_file: Path) -> bool:
        """Load schema from a specific file."""
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if schema_file.suffix == '.sql':
                return self._parse_sql_schema(content)
            elif schema_file.suffix == '.py':
                return self._parse_alembic_schema(content)
            
        except Exception as e:
            self.warnings.append(f"⚠️ Could not load schema from {schema_file}: {e}")
        
        return False
    
    def _parse_sql_schema(self, content: str) -> bool:
        """Parse SQL schema content."""
        # Extract CREATE TABLE statements
        table_pattern = r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)\s*\((.*?)\);'
        matches = re.findall(table_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for table_name, columns_def in matches:
            columns = {}
            
            # Parse column definitions
            for line in columns_def.split('\n'):
                line = line.strip()
                if line and not line.startswith('--') and not line.startswith('CONSTRAINT'):
                    # Extract column definition
                    col_match = re.match(r'(\w+)\s+([^,\s]+)', line)
                    if col_match:
                        col_name, col_type = col_match.groups()
                        columns[col_name.lower()] = col_type.upper()
            
            if columns:
                self.schema_tables[table_name.lower()] = columns
        
        return len(self.schema_tables) > 0
    
    def _parse_alembic_schema(self, content: str) -> bool:
        """Parse Alembic migration schema content."""
        # Look for create_table calls
        create_table_pattern = r'op\.create_table\(\s*[\'"](\w+)[\'"]'
        matches = re.findall(create_table_pattern, content)
        
        # This is a simplified parser - in practice, you'd want more sophisticated parsing
        for table_name in matches:
            if table_name.lower() not in self.schema_tables:
                self.schema_tables[table_name.lower()] = {}
        
        return len(matches) > 0
    
    def validate_model_tables(self) -> bool:
        """Validate that model tables exist in schema."""
        model_files = list((self.backend_root / "app/models").glob("*.py"))
        success = True
        
        for file_path in model_files:
            if file_path.name == "__init__.py":
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if (isinstance(node, ast.ClassDef) and
                        self._is_sqlalchemy_model(node)):
                        
                        table_name = self._get_table_name(node)
                        if table_name:
                            if table_name.lower() not in self.schema_tables:
                                self.warnings.append(
                                    f"⚠️ {file_path.relative_to(self.backend_root)}: "
                                    f"Model {node.name} references table '{table_name}' not found in schema"
                                )
            
            except Exception as e:
                self.errors.append(f"❌ Error parsing model {file_path}: {e}")
                success = False
        
        return success
    
    def validate_column_mappings(self) -> bool:
        """Validate column mappings between models and schema."""
        model_files = list((self.backend_root / "app/models").glob("*.py"))
        success = True
        
        for file_path in model_files:
            if file_path.name == "__init__.py":
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if (isinstance(node, ast.ClassDef) and
                        self._is_sqlalchemy_model(node)):
                        
                        table_name = self._get_table_name(node)
                        if table_name and table_name.lower() in self.schema_tables:
                            schema_columns = self.schema_tables[table_name.lower()]
                            model_columns = self._get_model_columns(node)
                            
                            # Check for column mismatches
                            for model_col, db_col in model_columns.items():
                                if db_col.lower() not in schema_columns:
                                    self.errors.append(
                                        f"❌ {file_path.relative_to(self.backend_root)}: "
                                        f"Model {node.name} column '{model_col}' maps to non-existent DB column '{db_col}'"
                                    )
                                    success = False
                            
                            # Check for unmapped schema columns (informational)
                            mapped_db_cols = set(col.lower() for col in model_columns.values())
                            unmapped_cols = set(schema_columns.keys()) - mapped_db_cols
                            
                            if unmapped_cols:
                                # Filter out common system columns
                                system_cols = {'created_at', 'updated_at', 'id'}
                                significant_unmapped = unmapped_cols - system_cols
                                
                                if significant_unmapped:
                                    self.warnings.append(
                                        f"⚠️ {file_path.relative_to(self.backend_root)}: "
                                        f"Model {node.name} doesn't map schema columns: {', '.join(significant_unmapped)}"
                                    )
            
            except Exception as e:
                self.errors.append(f"❌ Error validating columns in {file_path}: {e}")
                success = False
        
        return success
    
    def validate_relationships(self) -> bool:
        """Validate foreign key relationships."""
        model_files = list((self.backend_root / "app/models").glob("*.py"))
        
        for file_path in model_files:
            if file_path.name == "__init__.py":
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for ForeignKey references
                fk_pattern = r'ForeignKey\([\'"]([^\'"]+)[\'"]\)'
                matches = re.findall(fk_pattern, content)
                
                for fk_ref in matches:
                    # Parse table.column format
                    if '.' in fk_ref:
                        ref_table, ref_column = fk_ref.split('.', 1)
                        
                        if ref_table.lower() in self.schema_tables:
                            schema_columns = self.schema_tables[ref_table.lower()]
                            if ref_column.lower() not in schema_columns:
                                self.warnings.append(
                                    f"⚠️ {file_path.relative_to(self.backend_root)}: "
                                    f"ForeignKey references non-existent column '{fk_ref}'"
                                )
                        else:
                            self.warnings.append(
                                f"⚠️ {file_path.relative_to(self.backend_root)}: "
                                f"ForeignKey references non-existent table '{ref_table}'"
                            )
            
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        return True
    
    def _is_sqlalchemy_model(self, node: ast.ClassDef) -> bool:
        """Check if class is a SQLAlchemy model."""
        return any(
            (isinstance(base, ast.Name) and base.id == "Base") or
            (isinstance(base, ast.Attribute) and base.attr == "Base")
            for base in node.bases
        )
    
    def _get_table_name(self, node: ast.ClassDef) -> Optional[str]:
        """Get table name from model class."""
        for item in node.body:
            if (isinstance(item, ast.Assign) and
                any(isinstance(target, ast.Name) and target.id == "__tablename__"
                    for target in item.targets)):
                
                if isinstance(item.value, ast.Constant):
                    return item.value.value
        
        return None
    
    def _get_model_columns(self, node: ast.ClassDef) -> Dict[str, str]:
        """Get column mappings from model class."""
        columns = {}
        
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if it's a Column definition
                        if (isinstance(item.value, ast.Call) and
                            isinstance(item.value.func, ast.Name) and
                            item.value.func.id == "Column"):
                            
                            model_col_name = target.id
                            db_col_name = model_col_name
                            
                            # Check for column name mapping (first string argument)
                            if (item.value.args and 
                                isinstance(item.value.args[0], ast.Constant) and
                                isinstance(item.value.args[0].value, str)):
                                db_col_name = item.value.args[0].value
                            
                            columns[model_col_name] = db_col_name
        
        return columns
    
    def _print_results(self):
        """Print validation results."""
        if self.errors:
            print("\n❌ Database Model Issues:")
            for error in self.errors:
                print(f"  {error}")
        
        if self.warnings:
            print("\n⚠️ Database Model Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.errors and not self.warnings:
            print("✅ All database models are compatible!")
        elif not self.errors:
            print("✅ No critical database model issues (warnings only)")


def main():
    """Main entry point."""
    validator = DatabaseModelValidator()
    success = validator.validate()
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()