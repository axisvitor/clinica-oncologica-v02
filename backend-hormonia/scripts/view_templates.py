"""View all message templates - full content"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT name, content, variables, message_type, is_active FROM message_templates ORDER BY name"))
    
    templates = []
    for row in result:
        templates.append({
            "name": row[0],
            "content": row[1],
            "variables": row[2],
            "type": row[3],
            "active": row[4]
        })
    
    for i, t in enumerate(templates, 1):
        print(f"\n{'#'*60}")
        print(f"# TEMPLATE {i}: {t['name']}")
        print(f"# Type: {t['type']} | Active: {t['active']}")
        print(f"# Variables: {t['variables']}")
        print('#'*60)
        print(t['content'])
        print('#'*60)
