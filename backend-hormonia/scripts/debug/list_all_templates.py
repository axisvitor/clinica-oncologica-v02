"""
Script para listar todos os templates do sistema.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

with conn.cursor() as cur:
    print('=' * 60)
    print('1. message_templates (WhatsApp)')
    print('=' * 60)
    cur.execute('SELECT * FROM message_templates ORDER BY name')
    for r in cur.fetchall(): 
        print(f"  {r['name']} - Active: {r['is_active']}")
    
    print()
    print('=' * 60)
    print('2. flow_kinds (Tipos de Flow)')
    print('=' * 60)
    cur.execute('SELECT kind_key, display_name, is_active FROM flow_kinds ORDER BY kind_key')
    for r in cur.fetchall(): 
        print(f"  {r['kind_key']} - {r['display_name']} - Active: {r['is_active']}")
    
    print()
    print('=' * 60)
    print('3. flow_template_versions (Versões de Template)')
    print('=' * 60)
    cur.execute('SELECT template_name, version_number, is_active, description FROM flow_template_versions ORDER BY template_name')
    for r in cur.fetchall(): 
        print(f"  {r['template_name']} v{r['version_number']} - Active: {r['is_active']}")
    
    print()
    print('=' * 60)
    print('4. quiz_templates')
    print('=' * 60)
    cur.execute('SELECT name, is_active FROM quiz_templates ORDER BY name')
    for r in cur.fetchall(): 
        print(f"  {r['name']} - Active: {r['is_active']}")

conn.close()
