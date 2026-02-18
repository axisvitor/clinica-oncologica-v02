"""
Integration tests for SQLAlchemy custom types.

Tests EncryptedString, EncryptedText, EncryptedJSON with in-memory database.

NOTE: This test requires ENCRYPTION_KEY_CURRENT environment variable.
The test generates its own key in fixtures but imports fail at module load.
"""

import json
import os
import pytest
from datetime import date
from cryptography.fernet import Fernet

# Generate a valid key BEFORE any app imports
_test_key = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY_CURRENT"] = _test_key
os.environ["ENCRYPTION_CURRENT_KEY"] = _test_key  # Alternative var name

# Reset any existing singleton before imports
try:
    from app.core import encryption
    if hasattr(encryption, 'EncryptionService'):
        encryption.EncryptionService._instance = None
        encryption.EncryptionService._initialized = False
except Exception:
    pass

from sqlalchemy import create_engine, Column, Integer, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.encryption_types import EncryptedString, EncryptedText, EncryptedJSON, EncryptedDate

Base = declarative_base()


class EncryptionModel(Base):
    """Test model with encrypted fields."""
    __tablename__ = "test_encryption"

    id = Column(Integer, primary_key=True)
    encrypted_string = Column(EncryptedString(255))
    encrypted_text = Column(EncryptedText)
    encrypted_json = Column(EncryptedJSON)
    encrypted_date = Column(EncryptedDate)


@pytest.fixture
def encryption_key():
    """Generate a test encryption key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def db_session(encryption_key, monkeypatch):
    """Create in-memory SQLite database for testing."""
    # Set up environment
    monkeypatch.setenv("ENCRYPTION_KEY_CURRENT", encryption_key)

    # Reset singleton
    from app.core.encryption import EncryptionService
    EncryptionService._instance = None
    EncryptionService._initialized = False

    # Create engine and tables
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session, engine

    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)
    EncryptionService._instance = None
    EncryptionService._initialized = False


class TestEncryptedTypes:
    """Test SQLAlchemy encrypted types."""

    def test_encrypted_string_insert_and_select(self, db_session):
        """Test EncryptedString insert and select."""
        session, engine = db_session

        # Insert
        test_obj = EncryptionModel(
            id=1,
            encrypted_string="john@example.com"
        )
        session.add(test_obj)
        session.commit()

        # Verify encrypted in database
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT encrypted_string FROM test_encryption WHERE id=:id"),
                {"id": 1},
            ).fetchone()
        assert result[0].startswith("gAAAAA")  # Fernet format
        assert result[0] != "john@example.com"  # Encrypted

        # Verify decrypted in ORM
        retrieved = session.query(EncryptionModel).filter_by(id=1).first()
        assert retrieved.encrypted_string == "john@example.com"

    def test_encrypted_text_large_content(self, db_session):
        """Test EncryptedText with large content."""
        session, _ = db_session

        large_text = "A" * 10000  # 10KB
        test_obj = EncryptionModel(
            id=2,
            encrypted_text=large_text
        )
        session.add(test_obj)
        session.commit()

        # Retrieve and verify
        retrieved = session.query(EncryptionModel).filter_by(id=2).first()
        assert retrieved.encrypted_text == large_text

    def test_encrypted_json_dict(self, db_session):
        """Test EncryptedJSON with dictionary."""
        session, engine = db_session

        json_data = {
            "lab_results": ["test1", "test2"],
            "vitals": {"bp": "120/80", "temp": 37.5}
        }

        test_obj = EncryptionModel(
            id=3,
            encrypted_json=json_data
        )
        session.add(test_obj)
        session.commit()

        # Verify encrypted in database
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT encrypted_json FROM test_encryption WHERE id=:id"),
                {"id": 3},
            ).fetchone()
        assert result[0].startswith("gAAAAA")
        # Verify it's not raw JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(result[0])

        # Verify decrypted in ORM
        retrieved = session.query(EncryptionModel).filter_by(id=3).first()
        assert retrieved.encrypted_json == json_data

    def test_encrypted_json_list(self, db_session):
        """Test EncryptedJSON with list."""
        session, _ = db_session

        json_data = ["item1", "item2", "item3"]

        test_obj = EncryptionModel(
            id=4,
            encrypted_json=json_data
        )
        session.add(test_obj)
        session.commit()

        retrieved = session.query(EncryptionModel).filter_by(id=4).first()
        assert retrieved.encrypted_json == json_data

    def test_encrypted_date(self, db_session):
        """Test EncryptedDate."""
        session, engine = db_session

        test_date = date(1990, 5, 15)

        test_obj = EncryptionModel(
            id=5,
            encrypted_date=test_date
        )
        session.add(test_obj)
        session.commit()

        # Verify encrypted in database
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT encrypted_date FROM test_encryption WHERE id=:id"),
                {"id": 5},
            ).fetchone()
        assert result[0].startswith("gAAAAA")

        # Verify decrypted in ORM
        retrieved = session.query(EncryptionModel).filter_by(id=5).first()
        assert retrieved.encrypted_date == test_date

    def test_null_values(self, db_session):
        """Test that NULL values are handled correctly."""
        session, _ = db_session

        test_obj = EncryptionModel(
            id=6,
            encrypted_string=None,
            encrypted_text=None,
            encrypted_json=None,
            encrypted_date=None
        )
        session.add(test_obj)
        session.commit()

        retrieved = session.query(EncryptionModel).filter_by(id=6).first()
        assert retrieved.encrypted_string is None
        assert retrieved.encrypted_text is None
        assert retrieved.encrypted_json is None
        assert retrieved.encrypted_date is None

    def test_update_encrypted_field(self, db_session):
        """Test updating encrypted field."""
        session, _ = db_session

        # Insert
        test_obj = EncryptionModel(
            id=7,
            encrypted_string="original@example.com"
        )
        session.add(test_obj)
        session.commit()

        # Update
        test_obj.encrypted_string = "updated@example.com"
        session.commit()

        # Verify
        retrieved = session.query(EncryptionModel).filter_by(id=7).first()
        assert retrieved.encrypted_string == "updated@example.com"

    def test_unicode_in_encrypted_fields(self, db_session):
        """Test unicode content in encrypted fields."""
        session, _ = db_session

        test_obj = EncryptionModel(
            id=8,
            encrypted_string="Olá, こんにちは, 你好",
            encrypted_text="Unicode test: émojis 🔒🔐"
        )
        session.add(test_obj)
        session.commit()

        retrieved = session.query(EncryptionModel).filter_by(id=8).first()
        assert retrieved.encrypted_string == "Olá, こんにちは, 你好"
        assert retrieved.encrypted_text == "Unicode test: émojis 🔒🔐"
