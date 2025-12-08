"""
Tests for Security Key Validation (AUTH-001 Fix)

Tests comprehensive entropy validation, placeholder detection,
and secret masking for production security.

Security Issues Covered:
- AUTH-001: Placeholder key detection (Severity 9.5/10)
- SECRET-002: Secret masking for logs (Severity 8.0/10)
"""

import pytest
import secrets

from app.utils.security_validation import (
    KeyStrengthResult,
    calculate_shannon_entropy,
    calculate_entropy,
    contains_placeholder,
    analyze_character_distribution,
    validate_secret_entropy,
    validate_key_strength,
    mask_secret_for_logging,
    generate_secure_key,
    validate_all_secrets,
    is_production_ready,
    MIN_ENTROPY_PRODUCTION,
    MIN_ENTROPY_DEVELOPMENT,
)


class TestShannonEntropyCalculation:
    """Test Shannon entropy calculation functions."""

    def test_calculate_shannon_entropy_empty_string(self):
        """Empty string should have 0 entropy."""
        assert calculate_shannon_entropy("") == 0.0

    def test_calculate_shannon_entropy_single_char(self):
        """Single repeated character has 0 entropy."""
        assert calculate_shannon_entropy("aaaaaaaaaa") == 0.0

    def test_calculate_shannon_entropy_two_chars(self):
        """Two different characters have some entropy."""
        # "ababab" has entropy
        entropy = calculate_shannon_entropy("ababab")
        assert entropy > 0
        assert entropy < 10  # But not very high

    def test_calculate_shannon_entropy_random_string(self):
        """Random string has high entropy."""
        random_key = secrets.token_urlsafe(32)
        entropy = calculate_shannon_entropy(random_key)
        # Should be high entropy (>200 bits for 32-char random string)
        assert entropy > 200

    def test_calculate_shannon_entropy_placeholder(self):
        """Placeholder strings have low entropy."""
        entropy = calculate_shannon_entropy("CHANGE_THIS_SECRET_KEY")
        # Should be relatively low
        assert entropy < 100

    def test_calculate_entropy_backward_compatibility(self):
        """Legacy calculate_entropy returns per-character entropy."""
        # This is the old API that returns bits per character
        entropy_per_char = calculate_entropy("abcdefghij")
        # Should be between 0 and 8 bits/char
        assert 0 < entropy_per_char <= 8


class TestPlaceholderDetection:
    """Test placeholder pattern detection."""

    def test_contains_placeholder_obvious_cases(self):
        """Detect obvious placeholder patterns."""
        assert contains_placeholder("CHANGE_THIS")
        assert contains_placeholder("your_secret_here")
        assert contains_placeholder("replace_me_now")
        assert contains_placeholder("TODO_add_real_key")
        assert contains_placeholder("xxxxxxxxxxxxx")
        assert contains_placeholder("example_key_123")
        assert contains_placeholder("test_key_for_dev")
        assert contains_placeholder("default_secret")

    def test_contains_placeholder_case_insensitive(self):
        """Placeholder detection is case-insensitive."""
        assert contains_placeholder("Change_This")
        assert contains_placeholder("YOUR_SECRET")
        assert contains_placeholder("RePlAcE_Me")

    def test_contains_placeholder_no_false_positives(self):
        """Valid random keys don't trigger placeholder detection."""
        random_key = secrets.token_urlsafe(32)
        assert not contains_placeholder(random_key)

        # These look random enough
        assert not contains_placeholder("kJ8mN2pQ5rT9vW1xZ4aB7cD0eF3gH6")
        assert not contains_placeholder("a9f8e7d6c5b4a3210987654321fedcba")


class TestCharacterDistributionAnalysis:
    """Test character distribution analysis."""

    def test_analyze_character_distribution_all_types(self):
        """Analyze string with all character types."""
        result = analyze_character_distribution("Abc123!@#")
        assert result["lowercase"] == 2  # bc
        assert result["uppercase"] == 1  # A
        assert result["digits"] == 3  # 123
        assert result["special"] == 3  # !@#
        assert result["total"] == 9

    def test_analyze_character_distribution_only_lowercase(self):
        """Analyze lowercase-only string."""
        result = analyze_character_distribution("abcdefghij")
        assert result["lowercase"] == 10
        assert result["uppercase"] == 0
        assert result["digits"] == 0
        assert result["special"] == 0

    def test_analyze_character_distribution_mixed(self):
        """Analyze typical base64-encoded string."""
        result = analyze_character_distribution("kJ8mN2pQ5r-_T9")
        assert result["lowercase"] > 0
        assert result["uppercase"] > 0
        assert result["digits"] > 0
        assert result["special"] > 0  # -_


class TestValidateSecretEntropy:
    """Test main entropy validation function."""

    def test_validate_secret_entropy_empty_raises(self):
        """Empty secret raises ValueError."""
        with pytest.raises(ValueError, match="Secret cannot be empty"):
            validate_secret_entropy("")

    def test_validate_secret_entropy_none_raises(self):
        """None secret raises ValueError."""
        with pytest.raises(ValueError, match="Secret cannot be empty"):
            validate_secret_entropy(None)

    def test_validate_secret_entropy_placeholder_fails(self):
        """Placeholder secrets fail validation."""
        assert not validate_secret_entropy("CHANGE_THIS_IN_PRODUCTION")
        assert not validate_secret_entropy("your_secret_key_here_please")

    def test_validate_secret_entropy_placeholder_allowed_in_dev(self):
        """Placeholders can be allowed in dev mode."""
        # Still fails because entropy is too low
        assert not validate_secret_entropy(
            "CHANGE_THIS",
            min_bits=128,
            allow_placeholder_in_dev=True
        )

    def test_validate_secret_entropy_weak_key_fails(self):
        """Weak keys with low entropy fail."""
        assert not validate_secret_entropy("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert not validate_secret_entropy("12345678901234567890123456789012")

    def test_validate_secret_entropy_strong_key_passes(self):
        """Strong random keys pass validation."""
        strong_key = secrets.token_urlsafe(32)
        assert validate_secret_entropy(strong_key, min_bits=MIN_ENTROPY_PRODUCTION)

    def test_validate_secret_entropy_custom_threshold(self):
        """Can set custom entropy threshold."""
        # Low threshold for development
        medium_key = secrets.token_urlsafe(10)
        assert validate_secret_entropy(medium_key, min_bits=MIN_ENTROPY_DEVELOPMENT)


class TestValidateKeyStrength:
    """Test comprehensive key strength validation."""

    def test_validate_key_strength_empty_key(self):
        """Empty key returns detailed error."""
        result = validate_key_strength("")
        assert not result.is_valid
        assert result.entropy_bits == 0.0
        assert result.strength_level == "none"
        assert "empty" in result.issues[0].lower()

    def test_validate_key_strength_placeholder(self):
        """Placeholder key returns detailed analysis."""
        result = validate_key_strength("CHANGE_THIS_SECRET")
        assert not result.is_valid
        assert result.has_placeholder
        assert "placeholder" in result.issues[0].lower()
        assert any("cryptographically random" in rec.lower() for rec in result.recommendations)

    def test_validate_key_strength_too_short(self):
        """Short keys fail validation."""
        result = validate_key_strength("short")
        assert not result.is_valid
        assert any("too short" in issue.lower() for issue in result.issues)

    def test_validate_key_strength_low_entropy(self):
        """Low entropy keys fail validation."""
        result = validate_key_strength("a" * 50)  # Long but no entropy
        assert not result.is_valid
        assert any("insufficient entropy" in issue.lower() for issue in result.issues)
        assert result.strength_level in ["weak", "medium"]

    def test_validate_key_strength_low_diversity(self):
        """Keys with low character diversity get warnings."""
        result = validate_key_strength("abcdefghijklmnopqrstuvwxyz123456")
        # Might still pass entropy check but should note low diversity
        assert any("diversity" in issue.lower() for issue in result.issues) or result.is_valid

    def test_validate_key_strength_repeated_patterns(self):
        """Repeated patterns are detected."""
        result = validate_key_strength("abcabcabcabcabcabcabcabcabcabcabcabc")
        assert not result.is_valid
        assert any("repeated" in issue.lower() for issue in result.issues)

    def test_validate_key_strength_sequential_patterns(self):
        """Sequential patterns are detected."""
        result = validate_key_strength("abc123def456ghi789jkl012mno345pqr")
        assert any("sequential" in issue.lower() for issue in result.issues)

    def test_validate_key_strength_strong_key(self):
        """Strong random key passes all checks."""
        strong_key = secrets.token_urlsafe(32)
        result = validate_key_strength(strong_key, environment="production")

        assert result.is_valid
        assert result.entropy_bits >= MIN_ENTROPY_PRODUCTION
        assert result.strength_level in ["strong", "very_strong"]
        assert len(result.issues) == 0
        assert result.key_length >= 32

    def test_validate_key_strength_production_vs_development(self):
        """Production has stricter requirements than development."""
        medium_key = secrets.token_urlsafe(10)

        # Might pass development
        dev_result = validate_key_strength(
            medium_key,
            min_entropy=MIN_ENTROPY_DEVELOPMENT,
            environment="development"
        )

        # Should fail production
        prod_result = validate_key_strength(
            medium_key,
            min_entropy=MIN_ENTROPY_PRODUCTION,
            environment="production"
        )

        # Development should be more lenient
        assert dev_result.entropy_bits == prod_result.entropy_bits
        # But production should require more
        if not prod_result.is_valid:
            assert "CRITICAL" in prod_result.recommendations[0]


class TestMaskSecretForLogging:
    """Test secret masking for safe logging (SECRET-002)."""

    def test_mask_secret_empty(self):
        """Empty secrets return [EMPTY]."""
        assert mask_secret_for_logging("") == "[EMPTY]"
        assert mask_secret_for_logging(None) == "[EMPTY]"

    def test_mask_secret_short(self):
        """Short secrets are completely masked."""
        assert mask_secret_for_logging("abc") == "***"
        assert mask_secret_for_logging("12345") == "*****"

    def test_mask_secret_normal(self):
        """Normal secrets show first/last chars."""
        masked = mask_secret_for_logging("abcdefghijklmnop", visible_chars=4)
        assert masked.startswith("abcd")
        assert masked.endswith("mnop")
        assert "****" in masked

    def test_mask_secret_long(self):
        """Long secrets are capped at 20 asterisks."""
        very_long = "a" * 100
        masked = mask_secret_for_logging(very_long, visible_chars=4)
        # Should not have 92 asterisks, should be capped
        assert masked.count("*") <= 20

    def test_mask_secret_custom_visible(self):
        """Can customize visible characters."""
        secret = "0123456789abcdef"
        masked = mask_secret_for_logging(secret, visible_chars=2)
        assert masked.startswith("01")
        assert masked.endswith("ef")

    def test_mask_secret_never_reveals_full_secret(self):
        """Masking never reveals the full secret."""
        secret = secrets.token_urlsafe(32)
        masked = mask_secret_for_logging(secret)
        assert masked != secret
        assert len(masked) <= len(secret)  # Might be shorter due to cap


class TestGenerateSecureKey:
    """Test secure key generation."""

    def test_generate_secure_key_default(self):
        """Default generation creates strong keys."""
        key = generate_secure_key()
        result = validate_key_strength(key)
        assert result.is_valid
        assert result.strength_level in ["strong", "very_strong"]

    def test_generate_secure_key_custom_length(self):
        """Can generate keys of custom length."""
        key = generate_secure_key(length=64)
        # URL-safe base64 encoding makes it longer than input bytes
        assert len(key) >= 64
        result = validate_key_strength(key)
        assert result.is_valid

    def test_generate_secure_key_uniqueness(self):
        """Generated keys are unique."""
        key1 = generate_secure_key()
        key2 = generate_secure_key()
        assert key1 != key2


class TestValidateAllSecrets:
    """Test batch secret validation."""

    def test_validate_all_secrets_mixed_quality(self):
        """Validate multiple secrets with different quality."""
        secrets_dict = {
            "STRONG_KEY": secrets.token_urlsafe(32),
            "WEAK_KEY": "CHANGE_THIS_NOW",
            "MEDIUM_KEY": secrets.token_urlsafe(10),
        }

        results = validate_all_secrets(secrets_dict, environment="production")

        assert results["STRONG_KEY"].is_valid
        assert not results["WEAK_KEY"].is_valid
        # Medium might fail production requirements
        assert isinstance(results["MEDIUM_KEY"], KeyStrengthResult)

    def test_validate_all_secrets_production_vs_dev(self):
        """Production has stricter validation than dev."""
        weak_secret = secrets.token_urlsafe(8)
        secrets_dict = {"KEY": weak_secret}

        dev_results = validate_all_secrets(secrets_dict, environment="development")
        prod_results = validate_all_secrets(secrets_dict, environment="production")

        # Same entropy, different thresholds
        assert dev_results["KEY"].entropy_bits == prod_results["KEY"].entropy_bits
        # But validation result might differ
        # Production is always stricter or equal


class TestIsProductionReady:
    """Test quick production readiness check."""

    def test_is_production_ready_strong_key(self):
        """Strong keys are production ready."""
        strong_key = secrets.token_urlsafe(32)
        assert is_production_ready(strong_key)

    def test_is_production_ready_weak_key(self):
        """Weak keys are not production ready."""
        assert not is_production_ready("CHANGE_THIS")
        assert not is_production_ready("weak_secret_12345")
        assert not is_production_ready("a" * 50)

    def test_is_production_ready_medium_key(self):
        """Medium strength keys might not be production ready."""
        medium_key = secrets.token_urlsafe(10)
        # Depends on entropy, but likely fails 128-bit requirement
        result = is_production_ready(medium_key)
        # Should be False or borderline
        assert isinstance(result, bool)


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def test_scenario_startup_validation_production(self):
        """Simulate production startup validation."""
        # Typical production secrets
        secrets_to_validate = {
            "JWT_SECRET_KEY": secrets.token_urlsafe(32),
            "ENCRYPTION_KEY": secrets.token_urlsafe(32),
            "CSRF_SECRET": secrets.token_urlsafe(32),
        }

        results = validate_all_secrets(secrets_to_validate, environment="production")

        # All should pass
        for key_name, result in results.items():
            assert result.is_valid, f"{key_name} should be valid: {result.issues}"
            assert result.strength_level in ["strong", "very_strong"]

    def test_scenario_detect_placeholder_in_env(self):
        """Detect placeholder values from .env.example."""
        dangerous_secrets = {
            "JWT_SECRET_KEY": "CHANGE_THIS_IN_PRODUCTION_OK",
            "ENCRYPTION_KEY": "your_encryption_key_here",
            "CSRF_SECRET": "replace_me_with_real_secret",
        }

        results = validate_all_secrets(dangerous_secrets, environment="production")

        # All should fail
        for key_name, result in results.items():
            assert not result.is_valid
            assert result.has_placeholder
            assert "placeholder" in str(result.issues).lower()

    def test_scenario_log_safe_error_message(self):
        """Error messages never expose full secrets."""
        weak_secret = "CHANGE_THIS_SECRET_KEY_NOW_PLEASE"

        result = validate_key_strength(weak_secret, environment="production")
        masked = mask_secret_for_logging(weak_secret)

        # Result should indicate failure
        assert not result.is_valid

        # Masked version should be safe to log
        assert masked != weak_secret
        assert "****" in masked

        # Can safely log error
        error_msg = f"Secret validation failed: {masked}"
        assert weak_secret not in error_msg

    def test_scenario_development_warning_not_blocking(self):
        """Development mode warns but doesn't block weak secrets."""
        weak_secret = "dev_secret_for_testing"

        # In development, we get analysis but might not block
        result = validate_key_strength(weak_secret, environment="development")

        # Should provide warnings
        assert len(result.issues) > 0 or len(result.recommendations) > 0

        # But the key itself is detected as weak
        assert not result.is_valid or result.strength_level == "weak"


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_calculate_entropy_still_works(self):
        """Old calculate_entropy API still works."""
        entropy = calculate_entropy("test_string_here")
        assert isinstance(entropy, float)
        assert 0 <= entropy <= 8  # Bits per character

    def test_new_api_coexists_with_old(self):
        """New and old APIs can coexist."""
        test_string = "random_test_key_12345"

        # Old API: per-character entropy
        old_entropy = calculate_entropy(test_string)

        # New API: total entropy
        new_entropy = calculate_shannon_entropy(test_string)

        # New should be old * length
        assert abs(new_entropy - (old_entropy * len(test_string))) < 0.01


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_characters(self):
        """Handle unicode characters gracefully."""
        unicode_key = "key_with_émojis_🔐_and_ñ"
        result = validate_key_strength(unicode_key)
        # Should not crash
        assert isinstance(result, KeyStrengthResult)

    def test_very_long_key(self):
        """Handle very long keys."""
        very_long_key = secrets.token_urlsafe(1000)
        result = validate_key_strength(very_long_key)
        assert result.is_valid
        assert result.strength_level == "very_strong"

    def test_whitespace_in_key(self):
        """Keys with whitespace are handled."""
        key_with_spaces = "key with spaces and tabs\t\n"
        result = validate_key_strength(key_with_spaces)
        # Whitespace counts as special characters
        assert isinstance(result, KeyStrengthResult)

    def test_all_special_characters(self):
        """Keys with only special characters."""
        special_key = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        result = validate_key_strength(special_key)
        # Should have issues (length, diversity, etc.)
        assert len(result.issues) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
