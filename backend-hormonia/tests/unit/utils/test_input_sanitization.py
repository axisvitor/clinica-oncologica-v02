"""
Comprehensive unit tests for app.utils.input_sanitization module.
Tests input sanitization, validation, and security measures.
"""
import pytest
from unittest.mock import Mock, patch
from app.utils.input_sanitization import (
    InputSanitizer, get_sanitizer, sanitize_input
)


class TestInputSanitizer:
    """Test the InputSanitizer class."""

    @pytest.fixture
    def sanitizer(self):
        """Create InputSanitizer instance."""
        return InputSanitizer()

    def test_init_compiles_regex_patterns(self, sanitizer):
        """Test InputSanitizer initialization compiles regex patterns."""
        assert sanitizer.xss_regex is not None
        assert sanitizer.sql_regex is not None

        # Verify patterns can match known threats
        assert sanitizer.xss_regex.search("<script>alert('xss')</script>")
        assert sanitizer.sql_regex.search("SELECT * FROM users")

    def test_sanitize_string_basic(self, sanitizer):
        """Test basic string sanitization."""
        result = sanitizer.sanitize_string("Hello World")
        assert result == "Hello World"

    def test_sanitize_string_non_string_input(self, sanitizer):
        """Test sanitization of non-string input."""
        result = sanitizer.sanitize_string(123)
        assert result == "123"

    def test_sanitize_string_strip_whitespace(self, sanitizer):
        """Test whitespace stripping."""
        result = sanitizer.sanitize_string("  Hello World  ", strip_whitespace=True)
        assert result == "Hello World"

        result = sanitizer.sanitize_string("  Hello World  ", strip_whitespace=False)
        assert result == "  Hello World  "

    def test_sanitize_string_max_length_truncation(self, sanitizer):
        """Test string truncation when max_length is exceeded."""
        long_string = "a" * 100

        with patch('app.utils.input_sanitization.logger') as mock_logger:
            result = sanitizer.sanitize_string(long_string, max_length=50)

            assert len(result) == 50
            mock_logger.warning.assert_called_once()

    def test_sanitize_string_html_escape_default(self, sanitizer):
        """Test HTML escaping by default."""
        html_input = "<div>Hello &amp; World</div>"
        result = sanitizer.sanitize_string(html_input, allow_html=False)

        assert "&lt;div&gt;" in result
        assert "&amp;" in result

    def test_sanitize_string_allow_html(self, sanitizer):
        """Test HTML cleaning when allow_html=True."""
        html_input = "<p>Safe content</p><script>alert('xss')</script>"
        result = sanitizer.sanitize_string(html_input, allow_html=True)

        assert "<p>Safe content</p>" in result
        assert "<script>" not in result

    def test_sanitize_string_xss_detection(self, sanitizer):
        """Test XSS pattern detection and removal."""
        xss_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "onclick='alert(1)'",
            "<iframe src='evil'></iframe>"
        ]

        for xss_input in xss_inputs:
            with patch('app.utils.input_sanitization.logger') as mock_logger:
                result = sanitizer.sanitize_string(xss_input)

                # Should log warning and remove pattern
                mock_logger.warning.assert_called()
                assert len(result) < len(xss_input)

    def test_sanitize_string_sql_injection_detection(self, sanitizer):
        """Test SQL injection pattern detection and removal."""
        sql_inputs = [
            "SELECT * FROM users",
            "' OR 1=1 --",
            "UNION SELECT password",
            "DROP TABLE users"
        ]

        for sql_input in sql_inputs:
            with patch('app.utils.input_sanitization.logger') as mock_logger:
                result = sanitizer.sanitize_string(sql_input)

                # Should log warning and remove pattern
                mock_logger.warning.assert_called()
                assert len(result) < len(sql_input)

    def test_sanitize_email_valid(self, sanitizer):
        """Test email sanitization with valid email."""
        valid_emails = [
            "user@example.com",
            "test.email+tag@domain.co.uk",
            "user123@test-domain.org"
        ]

        for email in valid_emails:
            result = sanitizer.sanitize_email(email)
            assert result == email.lower()

    def test_sanitize_email_invalid(self, sanitizer):
        """Test email sanitization with invalid email."""
        invalid_emails = [
            "not-an-email",
            "@domain.com",
            "user@",
            "user space@domain.com",
            ""
        ]

        for email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email format"):
                sanitizer.sanitize_email(email)

    def test_sanitize_email_case_normalization(self, sanitizer):
        """Test email case normalization."""
        email = "User.Name@EXAMPLE.COM"
        result = sanitizer.sanitize_email(email)
        assert result == "user.name@example.com"

    def test_sanitize_email_length_limit(self, sanitizer):
        """Test email length limit enforcement."""
        long_email = "a" * 250 + "@example.com"

        with patch.object(sanitizer, 'sanitize_string') as mock_sanitize:
            mock_sanitize.return_value = "user@example.com"

            sanitizer.sanitize_email(long_email)

            mock_sanitize.assert_called_once_with(long_email, max_length=254, strip_whitespace=True)

    def test_sanitize_phone_basic(self, sanitizer):
        """Test basic phone number sanitization."""
        phone_inputs = [
            "+1234567890",
            "1234567890",
            "+55 11 98765-4321",
            "(11) 98765-4321"
        ]

        for phone in phone_inputs:
            result = sanitizer.sanitize_phone(phone)
            assert result.startswith("+")
            assert result.replace("+", "").isdigit()

    def test_sanitize_phone_removes_non_digits(self, sanitizer):
        """Test phone sanitization removes non-digit characters."""
        phone = "+55 (11) 98765-4321"
        result = sanitizer.sanitize_phone(phone)
        assert result == "+5511987654321"

    def test_sanitize_phone_adds_plus_prefix(self, sanitizer):
        """Test phone sanitization adds + prefix if missing."""
        phone = "1234567890"
        result = sanitizer.sanitize_phone(phone)
        assert result == "+1234567890"

    def test_sanitize_phone_invalid_length(self, sanitizer):
        """Test phone sanitization with invalid length."""
        invalid_phones = [
            "+123",  # Too short
            "+12345678901234567890"  # Too long
        ]

        for phone in invalid_phones:
            with pytest.raises(ValueError, match="Invalid phone number format"):
                sanitizer.sanitize_phone(phone)

    def test_sanitize_url_valid(self, sanitizer):
        """Test URL sanitization with valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://test.org/path",
            "https://subdomain.domain.com/path?query=value"
        ]

        for url in valid_urls:
            result = sanitizer.sanitize_url(url)
            assert result == url

    def test_sanitize_url_invalid_scheme(self, sanitizer):
        """Test URL sanitization with invalid scheme."""
        invalid_urls = [
            "ftp://example.com",
            "file:///etc/passwd",
            "javascript:alert(1)"
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError, match="URL scheme not allowed"):
                sanitizer.sanitize_url(url)

    def test_sanitize_url_custom_allowed_schemes(self, sanitizer):
        """Test URL sanitization with custom allowed schemes."""
        url = "ftp://example.com"
        result = sanitizer.sanitize_url(url, allowed_schemes=["ftp", "https"])
        assert result == url

    def test_sanitize_url_missing_domain(self, sanitizer):
        """Test URL sanitization with missing domain."""
        invalid_urls = [
            "https://",
            "http://",
            "not-a-url"
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid URL"):
                sanitizer.sanitize_url(url)

    def test_sanitize_url_length_limit(self, sanitizer):
        """Test URL length limit enforcement."""
        long_url = "https://example.com/" + "a" * 3000

        with patch.object(sanitizer, 'sanitize_string') as mock_sanitize:
            mock_sanitize.return_value = "https://example.com/truncated"

            sanitizer.sanitize_url(long_url)

            mock_sanitize.assert_called_once_with(long_url, max_length=2048, strip_whitespace=True)

    def test_sanitize_filename_basic(self, sanitizer):
        """Test basic filename sanitization."""
        filename = "document.pdf"
        result = sanitizer.sanitize_filename(filename)
        assert result == "document.pdf"

    def test_sanitize_filename_removes_dangerous_chars(self, sanitizer):
        """Test filename sanitization removes dangerous characters."""
        dangerous_filename = "doc<>ument|with:dangerous/chars.pdf"
        result = sanitizer.sanitize_filename(dangerous_filename)

        dangerous_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in dangerous_chars:
            assert char not in result

    def test_sanitize_filename_removes_directory_traversal(self, sanitizer):
        """Test filename sanitization removes directory traversal."""
        traversal_filename = "../../../etc/passwd"
        result = sanitizer.sanitize_filename(traversal_filename)
        assert ".." not in result

    def test_sanitize_filename_strips_dots_spaces(self, sanitizer):
        """Test filename sanitization strips leading/trailing dots and spaces."""
        filenames = [
            "  document.pdf  ",
            "...document.pdf...",
            " . document.pdf . "
        ]

        for filename in filenames:
            result = sanitizer.sanitize_filename(filename)
            assert not result.startswith(('.', ' '))
            assert not result.endswith(('.', ' '))

    def test_sanitize_filename_empty_after_cleaning(self, sanitizer):
        """Test filename sanitization with empty result after cleaning."""
        invalid_filenames = [
            "",
            "   ",
            "...",
            "<>?*|"
        ]

        for filename in invalid_filenames:
            with pytest.raises(ValueError, match="Invalid filename"):
                sanitizer.sanitize_filename(filename)

    def test_sanitize_filename_length_limit(self, sanitizer):
        """Test filename length limit enforcement."""
        long_filename = "a" * 300 + ".txt"
        result = sanitizer.sanitize_filename(long_filename)

        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_sanitize_filename_length_limit_no_extension(self, sanitizer):
        """Test filename length limit without extension."""
        long_filename = "a" * 300
        result = sanitizer.sanitize_filename(long_filename)

        assert len(result) <= 255

    def test_sanitize_dict_basic(self, sanitizer):
        """Test basic dictionary sanitization."""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        }

        result = sanitizer.sanitize_dict(data)

        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert result["age"] == 30

    def test_sanitize_dict_with_field_rules(self, sanitizer):
        """Test dictionary sanitization with field rules."""
        data = {
            "description": "  Long description  ",
            "content": "<p>HTML content</p>"
        }

        field_rules = {
            "description": {"max_length": 100, "strip_whitespace": True},
            "content": {"allow_html": True}
        }

        result = sanitizer.sanitize_dict(data, field_rules)

        assert result["description"] == "Long description"
        assert "<p>" in result["content"]

    def test_sanitize_dict_nested(self, sanitizer):
        """Test nested dictionary sanitization."""
        data = {
            "user": {
                "name": "John",
                "details": {
                    "bio": "  User bio  "
                }
            }
        }

        field_rules = {
            "user": {
                "nested_rules": {
                    "details": {
                        "nested_rules": {
                            "bio": {"strip_whitespace": True}
                        }
                    }
                }
            }
        }

        result = sanitizer.sanitize_dict(data, field_rules)
        assert result["user"]["details"]["bio"] == "User bio"

    def test_sanitize_dict_with_lists(self, sanitizer):
        """Test dictionary sanitization with list values."""
        data = {
            "tags": ["  tag1  ", "tag2", "  tag3  "],
            "numbers": [1, 2, 3]
        }

        result = sanitizer.sanitize_dict(data)

        # String items in lists should be sanitized
        assert "tag1" in result["tags"]
        assert result["numbers"] == [1, 2, 3]

    def test_validate_json_structure_valid(self, sanitizer):
        """Test JSON structure validation with valid structure."""
        valid_data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            },
            "array": [1, 2, 3]
        }

        result = sanitizer.validate_json_structure(valid_data, max_depth=5, max_keys=100)
        assert result is True

    def test_validate_json_structure_too_deep(self, sanitizer):
        """Test JSON structure validation with excessive nesting."""
        # Create deeply nested structure
        deep_data = {"level1": {"level2": {"level3": {"level4": {"level5": "value"}}}}}

        with pytest.raises(ValueError, match="JSON nesting too deep"):
            sanitizer.validate_json_structure(deep_data, max_depth=3)

    def test_validate_json_structure_too_many_keys(self, sanitizer):
        """Test JSON structure validation with too many keys."""
        # Create structure with many keys
        large_data = {f"key{i}": f"value{i}" for i in range(50)}

        with pytest.raises(ValueError, match="Too many keys in JSON"):
            sanitizer.validate_json_structure(large_data, max_keys=10)

    def test_validate_json_structure_with_arrays(self, sanitizer):
        """Test JSON structure validation with arrays."""
        data_with_arrays = {
            "users": [
                {"name": "user1", "details": {"age": 25}},
                {"name": "user2", "details": {"age": 30}}
            ]
        }

        result = sanitizer.validate_json_structure(data_with_arrays, max_depth=5, max_keys=20)
        assert result is True

    def test_validate_json_structure_complex_counting(self, sanitizer):
        """Test JSON structure validation counts keys correctly."""
        complex_data = {
            "users": [
                {"name": "user1", "age": 25},
                {"name": "user2", "age": 30}
            ],
            "settings": {
                "theme": "dark",
                "notifications": True
            }
        }

        # Total keys: users, settings, name (x2), age (x2), theme, notifications = 8 keys
        result = sanitizer.validate_json_structure(complex_data, max_keys=10)
        assert result is True

        with pytest.raises(ValueError, match="Too many keys"):
            sanitizer.validate_json_structure(complex_data, max_keys=5)


class TestSanitizerSingleton:
    """Test sanitizer singleton functionality."""

    def test_get_sanitizer_singleton(self):
        """Test get_sanitizer returns singleton instance."""
        with patch('app.utils.input_sanitization._sanitizer', None):
            sanitizer1 = get_sanitizer()
            sanitizer2 = get_sanitizer()

            assert sanitizer1 is sanitizer2
            assert isinstance(sanitizer1, InputSanitizer)


class TestSanitizeInputConvenience:
    """Test sanitize_input convenience function."""

    def test_sanitize_input_string_type(self):
        """Test sanitize_input with string field type."""
        result = sanitize_input("Hello World", field_type="string")
        assert result == "Hello World"

    def test_sanitize_input_email_type(self):
        """Test sanitize_input with email field type."""
        result = sanitize_input("USER@EXAMPLE.COM", field_type="email")
        assert result == "user@example.com"

    def test_sanitize_input_phone_type(self):
        """Test sanitize_input with phone field type."""
        result = sanitize_input("1234567890", field_type="phone")
        assert result == "+1234567890"

    def test_sanitize_input_url_type(self):
        """Test sanitize_input with URL field type."""
        result = sanitize_input("https://example.com", field_type="url")
        assert result == "https://example.com"

    def test_sanitize_input_filename_type(self):
        """Test sanitize_input with filename field type."""
        result = sanitize_input("document.pdf", field_type="filename")
        assert result == "document.pdf"

    def test_sanitize_input_unknown_type(self):
        """Test sanitize_input with unknown field type defaults to string."""
        result = sanitize_input("Hello World", field_type="unknown")
        assert result == "Hello World"

    def test_sanitize_input_with_kwargs(self):
        """Test sanitize_input passes kwargs to sanitization methods."""
        with patch('app.utils.input_sanitization.get_sanitizer') as mock_get_sanitizer:
            mock_sanitizer = Mock()
            mock_sanitizer.sanitize_url.return_value = "https://example.com"
            mock_get_sanitizer.return_value = mock_sanitizer

            sanitize_input("https://example.com", field_type="url", allowed_schemes=["https"])

            mock_sanitizer.sanitize_url.assert_called_once_with(
                "https://example.com", allowed_schemes=["https"]
            )


class TestInputSanitizerPatterns:
    """Test InputSanitizer pattern constants and regex compilation."""

    def test_allowed_tags_constant(self):
        """Test ALLOWED_TAGS constant is properly defined."""
        sanitizer = InputSanitizer()

        assert isinstance(sanitizer.ALLOWED_TAGS, list)
        assert len(sanitizer.ALLOWED_TAGS) > 0
        assert 'p' in sanitizer.ALLOWED_TAGS
        assert 'script' not in sanitizer.ALLOWED_TAGS

    def test_allowed_attributes_constant(self):
        """Test ALLOWED_ATTRIBUTES constant is properly defined."""
        sanitizer = InputSanitizer()

        assert isinstance(sanitizer.ALLOWED_ATTRIBUTES, dict)
        assert '*' in sanitizer.ALLOWED_ATTRIBUTES
        assert 'class' in sanitizer.ALLOWED_ATTRIBUTES['*']

    def test_xss_patterns_constant(self):
        """Test XSS_PATTERNS constant contains expected patterns."""
        sanitizer = InputSanitizer()

        assert isinstance(sanitizer.XSS_PATTERNS, list)
        assert len(sanitizer.XSS_PATTERNS) > 0

        # Check some known patterns exist
        patterns_str = '|'.join(sanitizer.XSS_PATTERNS)
        assert 'script' in patterns_str.lower()
        assert 'javascript' in patterns_str.lower()
        assert 'onclick' in patterns_str.lower()

    def test_sql_patterns_constant(self):
        """Test SQL_PATTERNS constant contains expected patterns."""
        sanitizer = InputSanitizer()

        assert isinstance(sanitizer.SQL_PATTERNS, list)
        assert len(sanitizer.SQL_PATTERNS) > 0

        # Check some known patterns exist
        patterns_str = '|'.join(sanitizer.SQL_PATTERNS)
        assert 'SELECT' in patterns_str.upper()
        assert 'UNION' in patterns_str.upper()
        assert 'DROP' in patterns_str.upper()

    def test_pattern_matching_case_insensitive(self):
        """Test patterns match case-insensitively."""
        sanitizer = InputSanitizer()

        # XSS patterns should match regardless of case
        test_cases = [
            "<SCRIPT>alert(1)</SCRIPT>",
            "<script>alert(1)</script>",
            "<Script>alert(1)</Script>"
        ]

        for case in test_cases:
            assert sanitizer.xss_regex.search(case) is not None

        # SQL patterns should match regardless of case
        sql_cases = [
            "SELECT * FROM users",
            "select * from users",
            "Select * From Users"
        ]

        for case in sql_cases:
            assert sanitizer.sql_regex.search(case) is not None

    def test_pattern_edge_cases(self):
        """Test pattern matching with edge cases."""
        sanitizer = InputSanitizer()

        # Test multiline XSS
        multiline_xss = """<script>
        alert('xss');
        </script>"""
        assert sanitizer.xss_regex.search(multiline_xss) is not None

        # Test SQL with extra whitespace
        spaced_sql = "SELECT   *   FROM   users"
        assert sanitizer.sql_regex.search(spaced_sql) is not None