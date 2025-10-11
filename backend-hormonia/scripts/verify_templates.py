#!/usr/bin/env python3
"""Verify imported templates in database"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("\n=== FLOW KINDS ===")
    result = conn.execute(text("SELECT kind_key, display_name FROM flow_kinds"))
    for row in result:
        print(f"  - {row[0]}: {row[1]}")

    print("\n=== FLOW TEMPLATE VERSIONS ===")
    result = conn.execute(text("SELECT template_name, version_number FROM flow_template_versions"))
    for row in result:
        print(f"  - {row[0]} (v{row[1]})")

    print("\n=== QUIZ TEMPLATES ===")
    result = conn.execute(text("SELECT name, version, time_limit_minutes FROM quiz_templates"))
    for row in result:
        print(f"  - {row[0]} v{row[1]} ({row[2]} minutes)")
