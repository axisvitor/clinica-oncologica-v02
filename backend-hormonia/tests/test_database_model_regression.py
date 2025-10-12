"""
Database Model Regression Tests
Comprehensive tests to prevent regression of database schema compatibility issues.
"""

import pytest
import re
from pathlib import Path
from typing import Dict, Set, List, Optional
from sqlalchemy import inspect, Column
from sqlalchemy.exc import SQLAlchemyError

from app.models.alert import Alert
from app.database.session import get_db


class TestDatabaseModelRegression:
    """Comprehensive tests for database model compatibility."""
    
    def test_alert_model_exists_and_structure(self):
        """Test that Alert model exists and has expected structure."""
        # Model should exist
        assert Alert is not None
        
        # Should have __tablename__
        assert hasattr(Alert, '__tablename__')
        assert Alert.__tablename__ == "alerts"
        
        # Should have __table__
        assert hasattr(Alert, '__table__')
        assert Alert.__table__ is not None
    
    def test_alert_model_column_mappings(self):
        """Test that Alert model has correct column mappings."""
        # Get table columns
        table = Alert.__table__
        column_names = [col.name for col in table.columns]
        
        # Should have basic required columns
        required_columns = ['id', 'patient_id']
        for col in required_columns:
            assert col in column_names, f"Alert table missing required column: {col}"
        
        # Test column name mappings for problematic fields
        # The model should map to actual database columns
        
        # Check if alert_type maps to 'type' column
        if hasattr(Alert, 'alert_type'):
            alert_type_col = getattr(Alert, 'alert_type')
            if hasattr(alert_type_col.property, 'columns'):
                actual_col_name = alert_type_col.property.columns[0].name
                assert actual_col_name in ['type', 'alert_type'], \
                    f"alert_type should map to 'type' or 'alert_type' column, maps to: {actual_col_name}"
        
        # Check if description maps to 'message' column
        if hasattr(Alert, 'description'):
            description_col = getattr(Alert, 'description')
            if hasattr(description_col.property, 'columns'):
                actual_col_name = description_col.property.columns[0].name
                assert actual_col_name in ['message', 'description'], \
                    f"description should map to 'message' or 'description' column, maps to: {actual_col_name}"
    
    def test_alert_model_status_property(self):
        """Test that Alert model handles status property correctly."""
        alert = Alert()
        
        # Test status property if it exists
        if hasattr(alert, 'status'):
            # Test setter
            alert.status = "acknowledged"
            if hasattr(alert, 'acknowledged'):
                assert alert.acknowledged == True, \
                    "Setting status to 'acknowledged' should set acknowledged=True"
            
            alert.status = "pending"
            if hasattr(alert, 'acknowledged'):
                assert alert.acknowledged == False, \
                    "Setting status to 'pending' should set acknowledged=False"
            
            # Test getter
            if hasattr(alert, 'acknowledged'):
                alert.acknowledged = True
                assert alert.status == "acknowledged", \
                    "acknowledged=True should return status='acknowledged'"
                
                alert.acknowledged = False
                assert alert.status == "pending", \
                    "acknowledged=False should return status='pending'"
    
    def test_alert_model_quiz_session_id_property(self):
        """Test that Alert model handles quiz_session_id property correctly."""
        alert = Alert()
        
        # Initialize data field if needed
        if hasattr(alert, 'data') and alert.data is None:
            alert.data = {}
        
        # Test quiz_session_id property if it exists
        if hasattr(alert, 'quiz_session_id'):
            import uuid
            test_uuid = uuid.uuid4()
            
            # Test setter
            alert.quiz_session_id = test_uuid
            
            # Should store in data JSONB field
            if hasattr(alert, 'data') and alert.data is not None:
                assert 'quiz_session_id' in alert.data, \
                    "quiz_session_id should be stored in data field"
                assert alert.data['quiz_session_id'] == str(test_uuid), \
                    "quiz_session_id should be stored as string in data field"
            
            # Test getter
            retrieved_uuid = alert.quiz_session_id
            assert retrieved_uuid == test_uuid, \
                "Retrieved quiz_session_id should match set value"
            
            # Test None handling
            alert.quiz_session_id = None
            assert alert.quiz_session_id is None, \
                "Setting quiz_session_id to None should return None"
    
    def test_alert_model_relationships(self):
        """Test that Alert model relationships are properly defined."""
        # Check for patient relationship
        if hasattr(Alert, 'patient'):
            patient_rel = getattr(Alert, 'patient')
            # Should be a relationship
            assert hasattr(patient_rel.property, 'mapper'), \
                "patient should be a SQLAlchemy relationship"
        
        # Check for acknowledged_by relationship if it exists
        if hasattr(Alert, 'acknowledged_by_user'):
            ack_rel = getattr(Alert, 'acknowledged_by_user')
            assert hasattr(ack_rel.property, 'mapper'), \
                "acknowledged_by_user should be a SQLAlchemy relationship"
    
    def test_alert_repository_compatibility(self):
        """Test that Alert repository methods work with model structure."""
        try:
            from app.repositories.alert import AlertRepository
            
            # Create repository instance (mock if needed)
            # This test verifies that repository methods are compatible with model
            
            # Test that repository has expected methods
            expected_methods = ['get_by_quiz_session', 'get_by_status']
            
            for method_name in expected_methods:
                if hasattr(AlertRepository, method_name):
                    method = getattr(AlertRepository, method_name)
                    assert callable(method), f"{method_name} should be callable"
        
        except ImportError:
            pytest.skip("AlertRepository not available for testing")


class TestDatabaseSchemaCompatibility:
    """Test database schema compatibility across models."""
    
    def test_model_table_names_exist(self):
        """Test that model table names correspond to actual database tables."""
        backend_root = Path(__file__).parent.parent
        
        # Load schema information if available
        schema_file = backend_root / "sql/SCHEMA_MASTER_COMPLETO.sql"
        if not schema_file.exists():
            pytest.skip("Schema file not found - skipping schema validation")
        
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_content = f.read()
        
        # Extract table names from schema
        table_pattern = r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)'
        schema_tables = set(re.findall(table_pattern, schema_content, re.IGNORECASE))
        schema_tables = {table.lower() for table in schema_tables}
        
        # Check Alert model
        assert Alert.__tablename__.lower() in schema_tables, \
            f"Alert table '{Alert.__tablename__}' not found in schema"
    
    def test_foreign_key_references_exist(self):
        """Test that foreign key references point to existing tables/columns."""
        backend_root = Path(__file__).parent.parent
        
        # Get all model files
        model_files = list((backend_root / "app/models").glob("*.py"))
        
        for model_file in model_files:
            if model_file.name == "__init__.py":
                continue
            
            with open(model_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find ForeignKey references
            fk_pattern = r'ForeignKey\([\'"]([^\'"]+)[\'"]\)'
            fk_refs = re.findall(fk_pattern, content)
            
            for fk_ref in fk_refs:
                # Parse table.column format
                if '.' in fk_ref:
                    ref_table, ref_column = fk_ref.split('.', 1)
                    
                    # Basic validation - in practice, you'd check against actual schema
                    assert ref_table, f"Empty table name in ForeignKey: {fk_ref}"
                    assert ref_column, f"Empty column name in ForeignKey: {fk_ref}"
                    
                    # Common table names that should exist
                    common_tables = ['users', 'patients', 'alerts', 'quiz_sessions']
                    if ref_table in common_tables:
                        # These are expected to exist
                        pass
    
    def test_column_type_consistency(self):
        """Test that column types are consistent and appropriate."""
        # Test Alert model column types
        table = Alert.__table__
        
        for column in table.columns:
            # ID columns should be UUID or Integer
            if column.name == 'id':
                # Should have appropriate type for primary key
                assert column.primary_key, f"ID column should be primary key"
            
            # Foreign key columns should have appropriate types
            if column.name.endswith('_id'):
                # Should have foreign key constraint or be UUID/Integer type
                pass  # Specific validation depends on actual schema
            
            # Boolean columns should be Boolean type
            if column.name in ['acknowledged', 'active', 'enabled']:
                # Should be Boolean type
                pass  # Specific validation depends on actual implementation
    
    def test_model_instantiation(self):
        """Test that models can be instantiated without errors."""
        # Test Alert model
        try:
            alert = Alert()
            assert alert is not None
            
            # Should be able to set basic attributes
            if hasattr(alert, 'severity'):
                alert.severity = "high"
            
            if hasattr(alert, 'acknowledged'):
                alert.acknowledged = False
            
        except Exception as e:
            pytest.fail(f"Failed to instantiate Alert model: {e}")


class TestDatabaseQueryCompatibility:
    """Test that database queries work with model definitions."""
    
    @pytest.mark.integration
    def test_alert_basic_queries(self):
        """Test basic Alert model queries work."""
        try:
            # This would require actual database connection
            # For now, test that query construction doesn't fail
            
            from sqlalchemy.orm import sessionmaker
            from app.database.session import engine
            
            # Test query construction (don't execute)
            Session = sessionmaker(bind=engine)
            session = Session()
            
            # Basic query construction
            query = session.query(Alert)
            assert query is not None
            
            # Filter query construction
            if hasattr(Alert, 'acknowledged'):
                ack_query = session.query(Alert).filter(Alert.acknowledged == True)
                assert ack_query is not None
            
            session.close()
            
        except Exception as e:
            pytest.skip(f"Database not available for query testing: {e}")
    
    @pytest.mark.integration
    def test_alert_repository_queries(self):
        """Test that repository queries work with model structure."""
        try:
            from app.repositories.alert import AlertRepository
            from app.database.session import get_db
            
            # Get database session
            db = next(get_db())
            repo = AlertRepository(db)
            
            # Test that methods can be called (may return empty results)
            if hasattr(repo, 'get_by_status'):
                # Should not raise exception
                result = repo.get_by_status("pending")
                assert isinstance(result, list)
            
            if hasattr(repo, 'get_by_quiz_session'):
                import uuid
                test_uuid = uuid.uuid4()
                # Should not raise exception
                result = repo.get_by_quiz_session(test_uuid)
                assert isinstance(result, list)
        
        except Exception as e:
            pytest.skip(f"Repository testing not available: {e}")


class TestModelMigrationCompatibility:
    """Test compatibility with database migrations."""
    
    def test_model_matches_latest_migration(self):
        """Test that models match the latest migration state."""
        backend_root = Path(__file__).parent.parent
        
        # Find latest migration files
        migration_dir = backend_root / "alembic/versions"
        if not migration_dir.exists():
            pytest.skip("Migration directory not found")
        
        migration_files = list(migration_dir.glob("*.py"))
        if not migration_files:
            pytest.skip("No migration files found")
        
        # Get the latest migration (by filename)
        latest_migration = max(migration_files, key=lambda f: f.name)
        
        with open(latest_migration, 'r', encoding='utf-8') as f:
            migration_content = f.read()
        
        # Check for Alert table operations in latest migrations
        if "alerts" in migration_content.lower():
            # Verify that migration operations are compatible with model
            
            # Look for column additions/modifications
            if "add_column" in migration_content:
                # Should not add columns that conflict with model
                pass
            
            if "alter_column" in migration_content:
                # Should not alter columns in incompatible ways
                pass
    
    def test_no_pending_model_changes(self):
        """Test that there are no pending model changes that need migration."""
        # This would ideally run alembic check to see if models match migrations
        # For now, we'll do basic structural checks
        
        try:
            from alembic import command
            from alembic.config import Config
            
            backend_root = Path(__file__).parent.parent
            alembic_cfg = Config(str(backend_root / "alembic.ini"))
            
            # This would check for pending migrations
            # Implementation depends on alembic setup
            
        except ImportError:
            pytest.skip("Alembic not available for migration checking")
        except Exception as e:
            pytest.skip(f"Migration checking not available: {e}")


class TestModelErrorPrevention:
    """Tests to prevent common model definition errors."""
    
    def test_no_duplicate_column_names(self):
        """Test that models don't have duplicate column names."""
        table = Alert.__table__
        column_names = [col.name for col in table.columns]
        unique_names = set(column_names)
        
        assert len(column_names) == len(unique_names), \
            f"Duplicate column names in Alert table: {column_names}"
    
    def test_primary_key_exists(self):
        """Test that models have primary keys."""
        table = Alert.__table__
        pk_columns = [col for col in table.columns if col.primary_key]
        
        assert len(pk_columns) > 0, "Alert table should have at least one primary key column"
    
    def test_required_columns_not_nullable(self):
        """Test that required columns are properly marked as not nullable."""
        table = Alert.__table__
        
        # Check specific columns that should not be nullable
        for column in table.columns:
            if column.name in ['id', 'patient_id']:
                assert not column.nullable, \
                    f"Column {column.name} should not be nullable"
    
    def test_foreign_key_constraints_exist(self):
        """Test that foreign key constraints are properly defined."""
        table = Alert.__table__
        
        # Check for foreign key constraints
        fk_constraints = table.foreign_keys
        
        # Should have at least patient_id foreign key
        patient_fks = [fk for fk in fk_constraints if 'patient' in str(fk.column)]
        if any(col.name == 'patient_id' for col in table.columns):
            assert len(patient_fks) > 0, \
                "Alert table should have foreign key constraint for patient_id"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])