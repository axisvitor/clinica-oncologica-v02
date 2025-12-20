"""
Unit tests for searchable hash service.

Tests hash determinism, uniqueness, case-insensitivity.
"""

import pytest
from app.core.searchable_hash import SearchableHash


@pytest.fixture
def setup_salt(monkeypatch):
    """Set up hash salt for testing."""
    monkeypatch.setenv("HASH_SALT", "test-salt-12345678909234567890123456789092")


class TestSearchableHash:
    """Test SearchableHash functionality."""

    def test_hash_email_determinism(self, setup_salt):
        """Test that same email produces same hash."""
        hash1 = SearchableHash.hash_email("john@example.com")
        hash2 = SearchableHash.hash_email("john@example.com")
        assert hash1 == hash2

    def test_hash_email_case_insensitive(self, setup_salt):
        """Test that email hash is case-insensitive."""
        hash1 = SearchableHash.hash_email("john@example.com")
        hash2 = SearchableHash.hash_email("JOHN@EXAMPLE.COM")
        hash3 = SearchableHash.hash_email("John@Example.Com")
        assert hash1 == hash2 == hash3

    def test_hash_email_uniqueness(self, setup_salt):
        """Test that different emails produce different hashes."""
        hash1 = SearchableHash.hash_email("john@example.com")
        hash2 = SearchableHash.hash_email("jane@example.com")
        assert hash1 != hash2

    def test_hash_email_none_returns_none(self, setup_salt):
        """Test that hashing None returns None."""
        assert SearchableHash.hash_email(None) is None
        assert SearchableHash.hash_email("") is None

    def test_hash_email_whitespace_trimmed(self, setup_salt):
        """Test that whitespace is trimmed."""
        hash1 = SearchableHash.hash_email("john@example.com")
        hash2 = SearchableHash.hash_email("  john@example.com  ")
        assert hash1 == hash2

    def test_hash_email_length(self, setup_salt):
        """Test that hash has correct length (SHA-256)."""
        hash_value = SearchableHash.hash_email("test@example.com")
        assert len(hash_value) == 64  # SHA-256 hex digest

    def test_hash_phone_determinism(self, setup_salt):
        """Test that same phone produces same hash."""
        hash1 = SearchableHash.hash_phone("+5511999999999")
        hash2 = SearchableHash.hash_phone("+5511999999999")
        assert hash1 == hash2

    def test_hash_phone_formatting_normalized(self, setup_salt):
        """Test that phone formatting is normalized."""
        hash1 = SearchableHash.hash_phone("+5511999999999")
        hash2 = SearchableHash.hash_phone("+55 11 99999-9999")
        hash3 = SearchableHash.hash_phone("+55 (11) 99999-9999")
        # All should produce the same hash after normalization
        assert hash1 == hash2 == hash3

    def test_hash_phone_none_returns_none(self, setup_salt):
        """Test that hashing None returns None."""
        assert SearchableHash.hash_phone(None) is None
        assert SearchableHash.hash_phone("") is None

    def test_hash_cpf_determinism(self, setup_salt):
        """Test that same CPF produces same hash."""
        hash1 = SearchableHash.hash_cpf("12345678909")
        hash2 = SearchableHash.hash_cpf("12345678909")
        assert hash1 == hash2

    def test_hash_cpf_formatting_normalized(self, setup_salt):
        """Test that CPF formatting is normalized."""
        hash1 = SearchableHash.hash_cpf("12345678909")
        hash2 = SearchableHash.hash_cpf("123.456.789-01")
        assert hash1 == hash2

    def test_hash_cpf_none_returns_none(self, setup_salt):
        """Test that hashing None returns None."""
        assert SearchableHash.hash_cpf(None) is None
        assert SearchableHash.hash_cpf("") is None

    def test_hash_generic_determinism(self, setup_salt):
        """Test that same value produces same hash."""
        hash1 = SearchableHash.hash_generic("test-value", "field1")
        hash2 = SearchableHash.hash_generic("test-value", "field1")
        assert hash1 == hash2

    def test_hash_generic_field_namespace(self, setup_salt):
        """Test that different field names produce different hashes."""
        hash1 = SearchableHash.hash_generic("same-value", "field1")
        hash2 = SearchableHash.hash_generic("same-value", "field2")
        # Different namespaces should produce different hashes
        assert hash1 != hash2

    def test_hash_generic_case_insensitive(self, setup_salt):
        """Test that generic hash is case-insensitive."""
        hash1 = SearchableHash.hash_generic("Test-Value", "field1")
        hash2 = SearchableHash.hash_generic("test-value", "field1")
        assert hash1 == hash2

    def test_different_field_types_different_hashes(self, setup_salt):
        """Test that same value in different fields produces different hashes."""
        email_hash = SearchableHash.hash_email("test@example.com")
        generic_hash = SearchableHash.hash_generic("test@example.com", "custom")
        # Field type namespacing should make hashes different
        assert email_hash != generic_hash

    def test_hash_without_salt_fails(self, monkeypatch):
        """Test that hashing fails without HASH_SALT."""
        monkeypatch.delenv("HASH_SALT", raising=False)
        monkeypatch.delenv("COMPLIANCE_HASH_SALT", raising=False)
        with pytest.raises(ValueError, match="HASH_SALT"):
            SearchableHash.hash_email("test@example.com")
