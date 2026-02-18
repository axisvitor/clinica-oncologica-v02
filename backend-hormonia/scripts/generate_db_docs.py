"""Script to generate database documentation from SQL schema."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect


def _get_docs_engine():
    db_url = os.getenv("DOCS_DATABASE_URL")
    if not db_url:
        raise SystemExit(
            "DOCS_DATABASE_URL not set. Refusing to run to avoid using the wrong DB."
        )

    connect_args = {}
    if db_url.startswith(("postgresql://", "postgresql+psycopg://")):
        connect_args["options"] = (
            "-c default_transaction_read_only=on "
            "-c statement_timeout=5000 "
            "-c lock_timeout=1000"
        )

    return create_engine(db_url, connect_args=connect_args)


def _format_type(type_obj) -> str:
    type_str = str(type_obj)
    type_name = type_obj.__class__.__name__.upper()
    if type_name == "ENUM":
        enum_name = getattr(type_obj, "name", None)
        if enum_name:
            return f"ENUM({enum_name})"
    return type_str


def generate_db_docs():
    engine = _get_docs_engine()
    inspector = inspect(engine)
    output_dir = Path("docs/database")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    table_names = inspector.get_table_names()
    
    # 1. Generate Schema Overview (SCHEMA.md)
    schema_md = "# Database Schema Documentation\n\n"
    schema_md += "## Tables Overview\n\n"
    schema_md += "| Table Name | Description |\n"
    schema_md += "| :--- | :--- |\n"
    
    for table in sorted(table_names):
        schema_md += f"| [{table}](tables/{table}.md) | |\n"
    
    # Mermaid ER Diagram
    schema_md += "\n## Entity Relationship Diagram\n\n"
    schema_md += "```mermaid\nerDiagram\n"
    
    for table_name in table_names:
        schema_md += f"    {table_name} {{\n"
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pks = pk_constraint.get('constrained_columns', [])

        for col in columns:
            col_name = col['name']
            col_type = _format_type(col['type']).replace(" ", "_")
            key_type = "PK" if col_name in pks else ""
            
            # Map common types to mermaid friendly types
            if "VARCHAR" in col_type: col_type = "string"
            elif "INTEGER" in col_type: col_type = "int"
            elif "UUID" in col_type: col_type = "uuid"
            elif "TIMESTAMP" in col_type: col_type = "datetime"
            elif "BOOLEAN" in col_type: col_type = "boolean"
            
            schema_md += f"        {col_type} {col_name} {key_type}\n"
        schema_md += "    }\n"
        
        # Add relationships
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            target_table = fk['referred_table']
            schema_md += f"    {table_name} }}o--|| {target_table} : \"references\"\n"
            
    schema_md += "```\n"

    with open(output_dir / "SCHEMA.md", "w", encoding="utf-8") as f:
        f.write(schema_md)
        
    print("Generated SCHEMA.md")

    # 2. Generate Individual Table Docs
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    for table_name in table_names:
        table_md = f"# Table: `{table_name}`\n\n"
        
        # Columns
        table_md += "## Columns\n\n"
        table_md += "| Name | Type | Nullable | Default | PK | FK |\n"
        table_md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pks = pk_constraint.get('constrained_columns', [])
        fks = inspector.get_foreign_keys(table_name)
        fk_map = {col: fk for fk in fks for col in fk['constrained_columns']}
        
        for col in columns:
            name = col['name']
            type_str = _format_type(col['type'])
            nullable = "✅" if col['nullable'] else "❌"
            default = f"`{col['default']}`" if col['default'] else "-"
            is_pk = "🔑" if name in pks else ""
            
            fk_info = ""
            if name in fk_map:
                tgt = fk_map[name]
                fk_info = f"➡️ [{tgt['referred_table']}]( {tgt['referred_table']}.md ).{tgt['referred_columns'][0]}"

            table_md += f"| **{name}** | `{type_str}` | {nullable} | {default} | {is_pk} | {fk_info} |\n"
            
        # Indexes
        indexes = inspector.get_indexes(table_name)
        if indexes:
            table_md += "\n## Indexes\n\n"
            table_md += "| Name | Unique | Columns |\n"
            table_md += "| :--- | :--- | :--- |\n"
            for idx in indexes:
                is_unique = "✅" if idx['unique'] else "❌"
                cols = ", ".join([str(c) if c else "<expr>" for c in idx['column_names']])
                table_md += f"| {idx['name']} | {is_unique} | `{cols}` |\n"
                
        with open(tables_dir / f"{table_name}.md", "w", encoding="utf-8") as f:
            f.write(table_md)
        print(f"Generated docs for {table_name}")

if __name__ == "__main__":
    generate_db_docs()
