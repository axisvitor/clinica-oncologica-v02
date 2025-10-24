import json

with open('database_schema_complete.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Table Name | Row Count")
print("-" * 50)
for table in data['tables']:
    print(f"{table['name']:40} | {table['row_count']}")

print(f"\nTotal tables: {len(data['tables'])}")
