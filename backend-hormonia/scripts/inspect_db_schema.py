import sys
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.url import make_url

# Initialize database URL from context (hardcoded for this script based on .env view)
DATABASE_URL = "postgresql+psycopg://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require"

def inspect_database():
    try:
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        
        tables_to_check = ["flow_analytics", "flow_messages", "flow_states", "quiz_questions"]
        
        print(f"Connected to {make_url(DATABASE_URL).database}")
        
        existing_tables = inspector.get_table_names()
        print(f"Total tables: {len(existing_tables)}")
        
        for table in tables_to_check:
            if table in existing_tables:
                print(f"\n--- Table: {table} ---")
                columns = inspector.get_columns(table)
                for col in columns:
                    print(f"- {col['name']} ({col['type']})")
            else:
                print(f"\n--- Table: {table} ---")
                print("DOES NOT EXIST")
                
    except Exception as e:
        print(f"Error inspecting database: {e}")

if __name__ == "__main__":
    inspect_database()
