"""Quick script to check patient data from RDS"""
import os
from dotenv import load_dotenv
load_dotenv()

import psycopg

# Fix SQLAlchemy URL format for pure psycopg
db_url = os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://')
conn = psycopg.connect(db_url)
cur = conn.cursor()

print("=== Patients with ACTIVE flow_state ===\n")
cur.execute('''
    SELECT id, name, current_day, treatment_start_date, flow_state::text, created_at 
    FROM patients 
    WHERE flow_state::text = 'ACTIVE' 
    ORDER BY created_at DESC 
    LIMIT 10
''')
rows = cur.fetchall()

print(f"{'ID':<36} | {'Name':<20} | Day | Start Date | State | Created")
print("-" * 110)
for row in rows:
    pid = str(row[0])
    name = (row[1] or "N/A")[:20]
    day = row[2]
    start = row[3] or "NULL"
    state = row[4]
    created = str(row[5])[:19] if row[5] else "N/A"
    print(f"{pid:<36} | {name:<20} | {day:>3} | {start} | {state} | {created}")

print("\n=== Summary: current_day values ===")
cur.execute('''
    SELECT current_day, COUNT(*) as cnt 
    FROM patients 
    WHERE flow_state::text = 'ACTIVE'
    GROUP BY current_day 
    ORDER BY current_day
''')
for row in cur.fetchall():
    print(f"  Day {row[0]}: {row[1]} patients")

print("\n=== Patients with NULL treatment_start_date ===")
cur.execute('''
    SELECT COUNT(*) FROM patients 
    WHERE flow_state::text = 'ACTIVE' AND treatment_start_date IS NULL
''')
null_count = cur.fetchone()[0]
print(f"  {null_count} patients have NULL treatment_start_date")

conn.close()
