"""Script to analyze database table usage in codebase."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from app.database import Base
import app.models  # noqa: F401 - ensure all models are registered


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

def analyze_usage():
    engine = _get_docs_engine()
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    
    # Get tables defined in SQLAlchemy models
    model_tables = set()
    for mapper in Base.registry.mappers:
        model_tables.add(mapper.mapped_table.name)
        
    # Analyze
    active_tables = db_tables.intersection(model_tables)
    orphan_tables = db_tables - model_tables
    missing_tables = model_tables - db_tables
    
    print(f"Total DB Tables: {len(db_tables)}")
    print(f"Total Models: {len(model_tables)}")
    print(f"Active (Used) Tables: {len(active_tables)}")
    
    if orphan_tables:
        print("\n⚠️  ORPHAN TABLES (Exist in DB but no active Model):")
        for t in sorted(orphan_tables):
            # Check if it's an association table or alembic table
            is_known = False
            if t == 'alembic_version': is_known = True
            if '_association' in t or '_tags' in t or 'permissions' in t: is_known = True # Guessing association tables
            
            status = "(Likely Association/System)" if is_known else "⚠️  POTENTIALLY UNUSED"
            print(f"  - {t} {status}")
            
    if missing_tables:
        print("\n❌ MISSING TABLES (Defined in Model but not in DB):")
        for t in sorted(missing_tables):
            print(f"  - {t}")

    # Generate Report
    report_path = Path("docs/database/USAGE_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Database Usage Analysis\n\n")
        f.write(f"**Generated at:** {os.popen('date').read().strip() or 'Now'}\n\n")
        
        f.write("## Summary\n")
        f.write(f"- **Total Tables in DB**: {len(db_tables)}\n")
        f.write(f"- **Mapped Models**: {len(model_tables)}\n")
        f.write(f"- **Active Tables**: {len(active_tables)}\n\n")
        
        f.write("## ⚠️ Orphan Tables (In DB, No Model)\n")
        f.write("These tables exist in the database but do not have a corresponding SQLAlchemy model loaded in `app/models`. They might be:\n")
        f.write("- Deprecated tables\n")
        f.write("- Raw SQL tables\n")
        f.write("- Many-to-Many association tables (implicit)\n\n")
        
        for t in sorted(orphan_tables):
            f.write(f"- `{t}`\n")
            
        f.write("\n## ❌ Missing Tables (In Model, No DB)\n")
        f.write("These models are defined in code but the table is missing in the DB (Migration pending?).\n\n")
        for t in sorted(missing_tables):
            f.write(f"- `{t}`\n")

    print(f"\nReport generated at {report_path}")

if __name__ == "__main__":
    analyze_usage()
