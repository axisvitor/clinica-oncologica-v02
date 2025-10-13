#!/usr/bin/env python3
import os
import sys
from sqlalchemy import create_engine, text

def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set")
        return 1
    engine = create_engine(url)
    with engine.connect() as conn:
        for table in [
            "flow_kinds",
            "flow_template_versions",
            "quiz_templates",
            "quiz_sessions",
            "quiz_responses",
            "messages",
        ]:
            print(f"\n== {table} ==")
            rows = conn.execute(text(
                """
                select column_name, data_type
                from information_schema.columns
                where table_schema = 'public' and table_name = :t
                order by ordinal_position
                """
            ), {"t": table}).mappings().all()
            for r in rows:
                print(f"{r['column_name']}: {r['data_type']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())


