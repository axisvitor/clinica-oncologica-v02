"""Script para listar todos os templates do sistema (via DATABASE_URL)."""

import os
import sys
from sqlalchemy import text

sys.path.append(os.getcwd())

from app.database import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        print("=" * 60)
        print("1. message_templates (WhatsApp)")
        print("=" * 60)
        for r in db.execute(text("SELECT name, is_active FROM message_templates ORDER BY name")):
            print(f"  {r[0]} - Active: {r[1]}")

        print()
        print("=" * 60)
        print("2. flow_kinds (Tipos de Flow)")
        print("=" * 60)
        for r in db.execute(
            text("SELECT kind_key, display_name, is_active FROM flow_kinds ORDER BY kind_key")
        ):
            print(f"  {r[0]} - {r[1]} - Active: {r[2]}")

        print()
        print("=" * 60)
        print("3. flow_template_versions (Versões de Template)")
        print("=" * 60)
        for r in db.execute(
            text(
                "SELECT template_name, version_number, is_active, description "
                "FROM flow_template_versions ORDER BY template_name"
            )
        ):
            print(f"  {r[0]} v{r[1]} - Active: {r[2]}")

        print()
        print("=" * 60)
        print("4. quiz_templates")
        print("=" * 60)
        for r in db.execute(text("SELECT name, is_active FROM quiz_templates ORDER BY name")):
            print(f"  {r[0]} - Active: {r[1]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
