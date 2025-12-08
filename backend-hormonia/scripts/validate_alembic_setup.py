#!/usr/bin/env python3
"""
Alembic Configuration Validator
Validates Alembic setup and migration chain integrity
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate_alembic_config():
    """Validate Alembic configuration files"""
    print("🔍 Validating Alembic configuration...\n")

    issues = []
    warnings = []

    # Check alembic.ini exists
    alembic_ini = Path(__file__).parent.parent / 'alembic.ini'
    if not alembic_ini.exists():
        issues.append("alembic.ini not found")
        return issues, warnings

    print(f"✓ Found alembic.ini at {alembic_ini}")

    # Check alembic directory
    alembic_dir = Path(__file__).parent.parent / 'alembic'
    if not alembic_dir.exists():
        issues.append("alembic/ directory not found")
        return issues, warnings

    print(f"✓ Found alembic directory at {alembic_dir}")

    # Check env.py exists
    env_py = alembic_dir / 'env.py'
    if not env_py.exists():
        issues.append("alembic/env.py not found")
    else:
        print(f"✓ Found env.py at {env_py}")

    # Check versions directory
    versions_dir = alembic_dir / 'versions'
    if not versions_dir.exists():
        issues.append("alembic/versions/ directory not found")
        return issues, warnings

    print(f"✓ Found versions directory at {versions_dir}")

    # Check migration files
    migration_files = sorted(versions_dir.glob('*.py'))
    migration_files = [f for f in migration_files if f.name != '__pycache__']

    if not migration_files:
        warnings.append("No migration files found in versions/")
    else:
        print(f"\n📋 Found {len(migration_files)} migration files:")
        for mf in migration_files:
            print(f"   - {mf.name}")

    # Validate migration file naming
    for mf in migration_files:
        if not mf.name.startswith(('001_', '002_', '003_', '004_', '005_', '006_', '007_', '008_', '009_', '010_', '011_', '012_', '013_', '014_', '015_', '016_', '017_', '018_')):
            warnings.append(f"Migration file {mf.name} doesn't follow naming convention")

    # Check for __init__.py
    init_py = versions_dir / '__init__.py'
    if not init_py.exists():
        # Create it if missing
        init_py.touch()
        print("\n✓ Created missing __init__.py in versions/")

    return issues, warnings


def validate_migration_chain():
    """Validate migration chain using alembic"""
    print("\n🔗 Validating migration chain...\n")

    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        # Get alembic config
        config_path = str(Path(__file__).parent.parent / 'alembic.ini')
        config = Config(config_path)

        # Get script directory
        script = ScriptDirectory.from_config(config)

        # Get all revisions
        revisions = list(script.walk_revisions())

        print(f"✓ Found {len(revisions)} revisions in chain")

        # Check for heads
        heads = script.get_heads()
        if not heads:
            return ["No migration heads found"], []

        print(f"✓ Current head(s): {', '.join(heads)}")

        # Check for branches
        if len(heads) > 1:
            return [], [f"Multiple migration heads detected: {heads}. This may indicate branching."]

        # Validate chain integrity
        current = script.get_current_head()
        if not current:
            return ["Could not determine current head"], []

        print(f"✓ Migration chain is linear and valid")

        return [], []

    except ImportError as e:
        return [f"Could not import alembic: {e}"], []
    except Exception as e:
        return [f"Error validating migration chain: {e}"], []


def check_database_connection():
    """Check if database is accessible"""
    print("\n🔌 Checking database connection...\n")

    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return ["DATABASE_URL not set"], []

    print(f"✓ DATABASE_URL is configured")

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(database_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ Database connection successful")
            print(f"  PostgreSQL version: {version.split()[1]}")

        # Check if alembic_version table exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'alembic_version'
                )
            """))
            has_alembic = result.scalar()

            if has_alembic:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                current_version = result.scalar()
                print(f"✓ Database is at migration: {current_version}")
            else:
                print(f"⚠️  alembic_version table does not exist (database not initialized)")

        return [], []

    except Exception as e:
        return [f"Database connection failed: {e}"], []


def main():
    """Main validation"""
    print("="*60)
    print("ALEMBIC SETUP VALIDATION")
    print("="*60 + "\n")

    all_issues = []
    all_warnings = []

    # Validate config
    issues, warnings = validate_alembic_config()
    all_issues.extend(issues)
    all_warnings.extend(warnings)

    # Validate chain
    issues, warnings = validate_migration_chain()
    all_issues.extend(issues)
    all_warnings.extend(warnings)

    # Check database
    issues, warnings = check_database_connection()
    all_issues.extend(issues)
    all_warnings.extend(warnings)

    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    if all_issues:
        print(f"\n❌ CRITICAL ISSUES ({len(all_issues)}):")
        for issue in all_issues:
            print(f"  - {issue}")

    if all_warnings:
        print(f"\n⚠️  WARNINGS ({len(all_warnings)}):")
        for warning in all_warnings:
            print(f"  - {warning}")

    if not all_issues and not all_warnings:
        print("\n✅ All checks passed! Alembic is properly configured.")
        return 0
    elif not all_issues:
        print("\n✅ No critical issues, but review warnings above.")
        return 0
    else:
        print("\n❌ Critical issues found. Please fix before running migrations.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
