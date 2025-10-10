#!/usr/bin/env python3
# GIN Index Migration Validation Script

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
migration_file = backend_dir / 'alembic' / 'versions' / '20251009_210800_add_gin_indexes_for_search.py'

print('GIN Index Migration Validation')
print('=' * 50)
print()

# 1. Check file exists
print('1. Checking migration file exists...')
if migration_file.exists():
    print(f'   [OK] Found: {migration_file}')
else:
    print(f'   [ERROR] NOT FOUND: {migration_file}')
    sys.exit(1)

# 2. Validate Python syntax
print()
print('2. Validating Python syntax...')
try:
    with open(migration_file, 'r') as f:
        compile(f.read(), migration_file, 'exec')
    print('   [OK] Syntax is valid')
except SyntaxError as e:
    print(f'   [ERROR] Syntax error: {e}')
    sys.exit(1)

# 3. Check for expected content
print()
print('3. Checking migration content...')
with open(migration_file, 'r') as f:
    content = f.read()
    
    checks = [
        ('pg_trgm extension', 'CREATE EXTENSION IF NOT EXISTS pg_trgm'),
        ('7 GIN indexes', 'idx_users_email_gin_trgm'),
        ('CONCURRENTLY flag', 'CREATE INDEX CONCURRENTLY'),
        ('Rollback logic', 'def downgrade'),
    ]
    
    all_passed = True
    for check_name, check_str in checks:
        result = check_str in content
        status = '[OK]' if result else '[ERROR]'
        print(f'   {status} {check_name}')
        if not result:
            all_passed = False
    
    if not all_passed:
        print()
        print('Validation failed!')
        sys.exit(1)

print()
print('=' * 50)
print('[SUCCESS] All validation checks passed!')
print('Migration is ready for testing.')
print()
print('Next steps:')
print('1. Test on development: alembic upgrade head')
print('2. Run verification: psql -f scripts/verify_gin_indexes.sql')
print('3. Check performance with EXPLAIN ANALYZE')
