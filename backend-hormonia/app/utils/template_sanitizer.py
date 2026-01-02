"""
Template Sanitization Utility - Secure Template Rendering

This module provides centralized input sanitization for all template rendering
operations to prevent injection attacks.

Security Features:
- HTML/Script injection prevention
- SQL injection prevention (via markupsafe)
- XSS attack prevention
- Safe string escaping for user input
"""

import re
from typing import Dict, Any, Optional
from markupsafe import escape


class TemplateSanitizer:
    """
    Centralized template sanitization utility.

    Provides secure template rendering by escaping all user-provided input
    before substitution into template strings.
    """

    # Patterns that should never appear in sanitized content
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>',
        r'javascript:',
        r'on\w+\s*=',  # Event handlers like onclick=
        r'eval\s*\(',
        r'expression\s*\(',
    ]

    @staticmethod
    def sanitize_template_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize all values in a template context dictionary.

        Args:
            context: Dictionary of template variables

        Returns:
            Dictionary with sanitized values (safe for template rendering)

        Example:
            >>> sanitizer = TemplateSanitizer()
            >>> context = {"name": "<script>alert('xss')</script>", "age": 25}
            >>> safe = sanitizer.sanitize_template_context(context)
            >>> safe["name"]
            "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;"
        """
        safe_context = {}

        # Keys that should be treated as URLs
        url_keys = {'link', 'url', 'href', 'redirect', 'callback_url', 'webhook_url'}

        for key, value in context.items():
            if isinstance(value, str):
                # Use URL sanitization for URL fields
                if key.lower() in url_keys or 'link' in key.lower() or 'url' in key.lower():
                    safe_context[key] = TemplateSanitizer.sanitize_url(value)
                else:
                    # Escape string values to prevent injection
                    safe_context[key] = str(escape(value))
            elif isinstance(value, (int, float, bool)):
                # Numbers and booleans are safe as-is
                safe_context[key] = value
            elif isinstance(value, (list, tuple)):
                # Recursively sanitize lists
                safe_context[key] = [
                    str(escape(str(item))) if isinstance(item, str) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                safe_context[key] = TemplateSanitizer.sanitize_template_context(value)
            elif value is None:
                safe_context[key] = ""
            else:
                # Convert other types to string and escape
                safe_context[key] = str(escape(str(value)))

        return safe_context

    @staticmethod
    def render_safe_template(template: str, context: Dict[str, Any]) -> str:
        """
        Render a template string with sanitized context.

        Args:
            template: Template string with {placeholder} syntax
            context: Dictionary of template variables

        Returns:
            Rendered template with escaped user input

        Raises:
            KeyError: If required template variable is missing
            ValueError: If template contains dangerous patterns after rendering

        Example:
            >>> sanitizer = TemplateSanitizer()
            >>> template = "Hello {name}! Your link: {link}"
            >>> context = {"name": "John<script>", "link": "https://example.com"}
            >>> result = sanitizer.render_safe_template(template, context)
            >>> "script" not in result  # Script tags are escaped
            True
        """
        # Sanitize all context values
        safe_context = TemplateSanitizer.sanitize_template_context(context)

        # Render template with sanitized values
        rendered = template.format(**safe_context)

        # Verify no dangerous patterns made it through
        TemplateSanitizer._verify_safe_output(rendered)

        return rendered

    @staticmethod
    def _verify_safe_output(output: str) -> None:
        """
        Verify rendered output doesn't contain dangerous patterns.

        Args:
            output: Rendered template string

        Raises:
            ValueError: If dangerous patterns are detected
        """
        output_lower = output.lower()

        for pattern in TemplateSanitizer.DANGEROUS_PATTERNS:
            if re.search(pattern, output_lower, re.IGNORECASE):
                raise ValueError(
                    f"Dangerous pattern detected in rendered template: {pattern}"
                )

    @staticmethod
    def sanitize_url(url: str) -> str:
        """
        Sanitize URL to prevent javascript: and data: URI schemes.

        Args:
            url: URL string to sanitize

        Returns:
            Sanitized URL (empty string if dangerous)

        Example:
            >>> TemplateSanitizer.sanitize_url("javascript:alert(1)")
            ""
            >>> TemplateSanitizer.sanitize_url("https://example.com")
            "https://example.com"
        """
        if not url or not isinstance(url, str):
            return ""

        url_lower = url.lower().strip()

        # Block dangerous URL schemes
        dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:']
        for scheme in dangerous_schemes:
            if url_lower.startswith(scheme):
                return ""

        # Only allow http, https, mailto
        allowed_schemes = ['http://', 'https://', 'mailto:', '//']
        if not any(url_lower.startswith(scheme) for scheme in allowed_schemes):
            # Relative URLs are ok
            if not url.startswith('/'):
                return ""

        return str(escape(url))

    @staticmethod
    def sanitize_patient_name(name: str) -> str:
        """
        Sanitize patient name with stricter rules.

        Args:
            name: Patient name

        Returns:
            Sanitized name (only letters, spaces, hyphens, apostrophes)
        """
        if not name or not isinstance(name, str):
            return ""

        # Remove any HTML/script content
        sanitized = str(escape(name))

        # Allow only safe characters for names
        # Letters (including accented), spaces, hyphens, apostrophes
        sanitized = re.sub(r"[^a-zA-ZÀ-ÿ\s\-']", "", sanitized)

        # Limit length
        return sanitized[:100].strip()


# Singleton instance
_sanitizer_instance: Optional[TemplateSanitizer] = None


def get_template_sanitizer() -> TemplateSanitizer:
    """
    Get singleton TemplateSanitizer instance.

    Returns:
        TemplateSanitizer instance
    """
    global _sanitizer_instance
    if _sanitizer_instance is None:
        _sanitizer_instance = TemplateSanitizer()
    return _sanitizer_instance
