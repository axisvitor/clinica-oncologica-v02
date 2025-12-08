#!/usr/bin/env python3
"""
Verify Upload Model Metadata Fix

This script verifies that the Upload model SQLAlchemy metadata conflict
has been properly resolved.

Usage:
    python3 scripts/verify_upload_metadata_fix.py
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_model_attributes():
    """Verify Upload model has correct attributes."""
    print("=" * 80)
    print("1. VERIFYING UPLOAD MODEL ATTRIBUTES")
    print("=" * 80)

    from app.models.upload import Upload

    # Check for file_metadata column
    has_file_metadata = hasattr(Upload, 'file_metadata')
    print(f"\n✅ Upload.file_metadata exists: {has_file_metadata}")

    if not has_file_metadata:
        print("❌ FAILED: Upload.file_metadata column not found!")
        return False

    # Check that metadata is SQLAlchemy's MetaData object
    metadata_type = type(Upload.metadata).__name__
    is_metadata_object = metadata_type == 'MetaData'
    print(f"✅ Upload.metadata is SQLAlchemy MetaData: {is_metadata_object}")

    if not is_metadata_object:
        print(f"❌ FAILED: Upload.metadata is {metadata_type}, not MetaData!")
        return False

    # Verify column type
    column_info = Upload.__table__.columns.get('file_metadata')
    if column_info is not None:
        print(f"✅ file_metadata column type: {column_info.type}")
    else:
        print("❌ FAILED: file_metadata column not in __table__.columns!")
        return False

    print("\n✅ All model attribute checks passed!")
    return True


def verify_no_conflicts():
    """Verify no attribute access conflicts."""
    print("\n" + "=" * 80)
    print("2. VERIFYING NO ATTRIBUTE CONFLICTS")
    print("=" * 80)

    from app.models.upload import Upload
    from uuid import uuid4

    try:
        # Try to create instance with file_metadata
        upload = Upload(
            user_id=uuid4(),
            file_name="test.jpg",
            file_size=1024,
            storage_path="/uploads/test.jpg",
            file_metadata={"test": "data", "patient_id": "123"}
        )

        # Verify file_metadata accessible
        metadata_value = upload.file_metadata
        print(f"\n✅ Can set and get file_metadata: {metadata_value}")

        # Verify SQLAlchemy metadata still works
        table_name = Upload.metadata.tables.get('uploads')
        if table_name is not None:
            print(f"✅ SQLAlchemy metadata accessible: {table_name}")
        else:
            print("⚠️  WARNING: 'uploads' table not in metadata (may be normal if not bound)")

        print("\n✅ No attribute conflicts detected!")
        return True

    except Exception as e:
        print(f"\n❌ FAILED: Attribute conflict detected: {e}")
        return False


def verify_migration_exists():
    """Verify migration file exists."""
    print("\n" + "=" * 80)
    print("3. VERIFYING MIGRATION FILE")
    print("=" * 80)

    migration_path = Path(__file__).parent.parent / "alembic" / "versions" / "013_rename_upload_metadata_column.py"

    if migration_path.exists():
        print(f"\n✅ Migration file exists: {migration_path.name}")

        # Check migration content
        content = migration_path.read_text()

        checks = {
            "Has upgrade function": "def upgrade():" in content,
            "Has downgrade function": "def downgrade():" in content,
            "Renames to file_metadata": "file_metadata" in content,
            "Has existence checks": "information_schema.columns" in content,
            "Has JSONB type": "JSONB" in content or "jsonb" in content.lower(),
        }

        all_passed = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check}: {passed}")
            if not passed:
                all_passed = False

        if all_passed:
            print("\n✅ Migration file validation passed!")
            return True
        else:
            print("\n❌ FAILED: Migration file validation failed!")
            return False
    else:
        print(f"\n❌ FAILED: Migration file not found at {migration_path}")
        return False


def verify_no_old_references():
    """Verify no old 'metadata' column references in code."""
    print("\n" + "=" * 80)
    print("4. VERIFYING NO OLD REFERENCES")
    print("=" * 80)

    # This is a simple check - more thorough checking would use grep
    from app.models.upload import Upload

    # Get Upload model source
    import inspect
    source = inspect.getsource(Upload)

    # Check for old column definition (should not exist)
    has_old_metadata = "metadata = Column(" in source and "file_metadata" not in source.split("metadata = Column(")[0]

    if has_old_metadata:
        print("\n❌ FAILED: Found old 'metadata = Column(' in Upload model!")
        return False
    else:
        print("\n✅ No old 'metadata = Column(' found in Upload model")

    # Verify file_metadata exists in source
    has_file_metadata = "file_metadata = Column(" in source

    if has_file_metadata:
        print("✅ Found 'file_metadata = Column(' in Upload model")
    else:
        print("❌ FAILED: 'file_metadata = Column(' not found in Upload model!")
        return False

    print("\n✅ No old references found!")
    return True


def main():
    """Run all verification checks."""
    print("\n" + "=" * 80)
    print("UPLOAD MODEL METADATA FIX VERIFICATION")
    print("=" * 80)

    results = {
        "Model Attributes": verify_model_attributes(),
        "No Conflicts": verify_no_conflicts(),
        "Migration Exists": verify_migration_exists(),
        "No Old References": verify_no_old_references(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    all_passed = True
    for check, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"\n{status}: {check}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Upload model fix verified!")
        print("=" * 80)
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Review errors above")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
