#!/usr/bin/env python3
"""Inspecionar schema da tabela patients."""

from sqlalchemy import create_engine, inspect
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
inspector = inspect(engine)

print("=" * 70)
print("SCHEMA DA TABELA PATIENTS")
print("=" * 70)

columns = inspector.get_columns("patients")
for col in columns:
    nullable = "NULL" if col['nullable'] else "NOT NULL"
    default = f" DEFAULT {col['default']}" if col['default'] else ""
    print(f"  {col['name']:<25} {str(col['type']):<20} {nullable}{default}")

print("=" * 70)
