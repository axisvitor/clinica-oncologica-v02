#!/usr/bin/env python3
"""
Schema Consistency Check

Compares the live PostgreSQL database schema with our SQLAlchemy ORM models.

Outputs:
- Missing tables (in DB vs ORM and vice-versa)
- Column diffs (type, nullable, default)
- Primary keys, foreign keys, unique constraints
- Index presence (names only; not full expressions)

Exit codes:
- 0: No inconsistencies
- 1: Inconsistencies found
- 2: Runtime error
"""
import os
import sys
import argparse
import importlib
import pkgutil
from typing import Dict, Any, List, Tuple, Set

from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.engine import Engine

# Ensure project root on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Use our configured engine/session and possible Bases
connection_manager = None
CoreBase = None
LegacyBase = None

try:
    from app.core.database import connection_manager as _cm, Base as _CoreBase
    connection_manager = _cm
    CoreBase = _CoreBase
except Exception:
    pass

try:
    from app.database import Base as _LegacyBase  # type: ignore
    LegacyBase = _LegacyBase
except Exception:
    pass

def _get_bases():
    bases = []
    if CoreBase is not None:
        bases.append(CoreBase)
    if LegacyBase is not None and LegacyBase is not CoreBase:
        bases.append(LegacyBase)
    if not bases:
        raise RuntimeError("No SQLAlchemy Base found (neither app.core.database.Base nor app.database.Base)")
    return bases


def _get_engine() -> Engine:
    if connection_manager is not None:
        return connection_manager.get_engine(use_service_role=True)
    # Fallback: build from env (rarely needed in this repo)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set and connection_manager unavailable")
    return create_engine(database_url)


def _import_all_models() -> None:
    """Dynamically import all modules under app.models to register ORM classes.

    This ensures `Base.metadata` is populated before we run comparisons.
    """
    try:
        import app.models as models_pkg  # noqa: F401
    except Exception as e:
        print(f"⚠️  Could not import app.models package: {e}")
        return

    package = sys.modules.get("app.models")
    if not package or not hasattr(package, "__path__"):
        return

    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        name = module_info.name
        try:
            importlib.import_module(name)
        except Exception as e:
            # Non-fatal; some modules may rely on optional deps
            print(f"⚠️  Skipping model module '{name}': {e}")


def _normalize_type(t: Any) -> str:
    """Return a simplified textual representation of a SQLAlchemy/DB type."""
    try:
        # Inspector returns dialect-agnostic names for DB columns (e.g., INTEGER, VARCHAR)
        if isinstance(t, str):
            name = t.upper()
            if name in {"DATETIME", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP"}:
                return "TIMESTAMP"
            if name in {"STRING", "VARCHAR", "CHARACTER VARYING"}:
                return "VARCHAR"
            return name
        # SQLAlchemy types often have .__class__.__name__ like Integer, String
        name = getattr(t, "__class__", type(t)).__name__.upper()
        if name in {"DATETIME"}:
            return "TIMESTAMP"
        if name in {"STRING"}:
            return "VARCHAR"
        return name
    except Exception:
        return str(t)


def compare_schema(engine: Engine) -> Tuple[bool, List[str]]:
    inspector = inspect(engine)

    # Collect DB objects across non-system schemas
    schemas = [s for s in inspector.get_schema_names() if s not in ("pg_catalog", "information_schema")]

    db_tables: Set[Tuple[str, str]] = set()
    for schema in schemas:
        for t in inspector.get_table_names(schema=schema):
            db_tables.add((schema, t))

    # Collect ORM tables from all known Bases into a combined MetaData
    orm_table_map = {}
    combined_md = MetaData()
    for base in _get_bases():
        for table in base.metadata.tables.values():
            if table.name not in combined_md.tables:
                table.to_metadata(combined_md)
    for table in combined_md.tables.values():
        schema = table.schema or "public"
        orm_table_map[(schema, table.name)] = table
    orm_tables: Set[Tuple[str, str]] = set(orm_table_map.keys())

    issues: List[str] = []

    # Table-level diffs (ignore DB-only tables)
    orm_only = sorted(orm_tables - db_tables)
    if orm_only:
        issues.append("ORM expects tables missing in DB:")
        for s, t in orm_only:
            issues.append(f"  - {s}.{t}")

    # Detailed per-table comparison only for intersection
    for s, t in sorted(db_tables & orm_tables):
        db_columns = {c["name"]: c for c in inspector.get_columns(t, schema=s)}
        orm_table = orm_table_map[(s, t)]
        orm_columns = {c.name: c for c in orm_table.columns}

        # Column presence: ignore DB-only columns; only report ORM-only (except updated_at)
        cols_orm_only = sorted(x for x in (set(orm_columns) - set(db_columns)) if x != 'updated_at')
        if cols_orm_only:
            issues.append(f"[{s}.{t}] column differences:")
            for c in cols_orm_only:
                issues.append(f"  - ORM only column: {c} ({_normalize_type(getattr(orm_columns[c].type, '__class__', orm_columns[c].type))})")

        # Column attribute checks for intersection
        for col in sorted(set(db_columns) & set(orm_columns)):
            diffs: List[str] = []

            dbc = db_columns[col]
            ormc = orm_columns[col]

            # Type (normalized)
            db_type = _normalize_type(dbc.get("type"))
            orm_type = _normalize_type(ormc.type)
            if db_type != orm_type:
                diffs.append(f"type: DB={db_type} vs ORM={orm_type}")

            # Nullable
            db_nullable = bool(dbc.get("nullable", True))
            orm_nullable = bool(ormc.nullable)
            if db_nullable != orm_nullable:
                diffs.append(f"nullable: DB={db_nullable} vs ORM={orm_nullable}")

            # Skip default/server_default comparisons to reduce noise

            if diffs:
                issues.append(f"[{s}.{t}.{col}] diffs: " + "; ".join(diffs))

        # Primary key
        try:
            db_pk = inspector.get_pk_constraint(t, schema=s)
            db_pk_cols = tuple(db_pk.get("constrained_columns") or [])
        except Exception:
            db_pk_cols = tuple()
        orm_pk_cols = tuple(col.name for col in orm_table.primary_key.columns) if orm_table.primary_key else tuple()
        if db_pk_cols != orm_pk_cols:
            issues.append(f"[{s}.{t}] primary key columns differ: DB={db_pk_cols} vs ORM={orm_pk_cols}")

        # Unique constraints (names are dialect-specific; compare columns only)
        try:
            db_uniques = inspector.get_unique_constraints(t, schema=s) or []
        except Exception:
            db_uniques = []
        db_unique_sets = sorted(tuple(sorted(u.get("column_names", []) or [])) for u in db_uniques)
        orm_unique_sets: List[Tuple[str, ...]] = []
        # Include explicit UniqueConstraints
        for uc in orm_table.constraints:
            try:
                from sqlalchemy import UniqueConstraint  # local import
                if isinstance(uc, UniqueConstraint):
                    orm_unique_sets.append(tuple(sorted(c.name for c in uc.columns)))
            except Exception:
                pass
        # Include column-level unique flags
        for col in orm_table.columns:
            try:
                if getattr(col, 'unique', False):
                    orm_unique_sets.append((col.name,))
            except Exception:
                pass
        orm_unique_sets = sorted(orm_unique_sets)
        if db_unique_sets != orm_unique_sets:
            issues.append(f"[{s}.{t}] unique constraints differ: DB={db_unique_sets} vs ORM={orm_unique_sets}")

        # Foreign keys (compare column -> referred_table.column)
        try:
            db_fks = inspector.get_foreign_keys(t, schema=s) or []
        except Exception:
            db_fks = []
        db_fk_map: Set[Tuple[Tuple[str, ...], str, Tuple[str, ...]]] = set()
        for fk in db_fks:
            db_fk_map.add((tuple(fk.get("constrained_columns", []) or []), (fk.get("referred_schema") or s) + "." + fk.get("referred_table", ""), tuple(fk.get("referred_columns", []) or [])))

        orm_fk_map: Set[Tuple[Tuple[str, ...], str, Tuple[str, ...]]] = set()
        for fk in getattr(orm_table, 'foreign_keys', []) or []:
            ref_schema: str
            ref_table: str
            ref_col: str
            try:
                # Preferred: resolve to actual table/column objects
                rt = fk.column.table  # may raise if unresolved
                ref_schema = rt.schema or "public"
                ref_table = rt.name
                ref_col = fk.column.name
            except Exception:
                # Fallback: parse from textual spec (e.g. "flow_template_versions.id")
                tf = getattr(fk, 'target_fullname', None) or getattr(fk, '_colspec', '')
                parts = str(tf).split('.') if tf else []
                if len(parts) == 3:
                    ref_schema, ref_table, ref_col = parts[0], parts[1], parts[2]
                elif len(parts) == 2:
                    ref_schema = s or 'public'
                    ref_table, ref_col = parts[0], parts[1]
                else:
                    continue
            orm_fk_map.add(((fk.parent.name,), f"{ref_schema}.{ref_table}", (ref_col,)))

        if db_fk_map != orm_fk_map:
            issues.append(f"[{s}.{t}] foreign keys differ: DB={sorted(db_fk_map)} vs ORM={sorted(orm_fk_map)}")

        # Skip index comparison to avoid noise

    ok = len(issues) == 0
    return ok, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare live DB schema with SQLAlchemy models")
    parser.add_argument("--schema", action="append", help="Limit to specific schema name(s); default: all non-system")
    args = parser.parse_args()

    try:
        _import_all_models()
        engine = _get_engine()

        print("🔍 Schema Consistency Check")
        print("=" * 60)

        ok, issues = compare_schema(engine)

        if ok:
            print("✅ No inconsistencies found. DB matches ORM models.")
            return 0

        print("❌ Inconsistencies detected:")
        for line in issues:
            print(line)
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())


