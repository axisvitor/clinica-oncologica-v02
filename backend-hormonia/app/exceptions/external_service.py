"""External service exception handling."""


class ExternalServiceError(Exception):
    """Base exception for external service errors."""
    
    def __init__(self, message: str, service: str = None, status_code: int = None):
        """Initialize external service error.
        
        Args:
            message: Error message
            service: Name of the external service
            status_code: HTTP status code if applicable
        """
        self.message = message
        self.service = service
        self.status_code = status_code
        super().__init__(self.message)
        
    def __str__(self):
        """String representation of the error."""
        parts = [self.message]
        if self.service:
            parts.insert(0, f"[{self.service}]")
        if self.status_code:
            parts.append(f"(Status: {self.status_code})")
        return " ".join(parts)


class APITimeoutError(ExternalServiceError):
    """Exception raised when an API call times out."""
    
    def __init__(self, message: str = "API request timed out", service: str = None):
        super().__init__(message, service, status_code=408)


class APIRateLimitError(ExternalServiceError):
    """Exception raised when API rate limit is exceeded."""
    
    def __init__(self, message: str = "API rate limit exceeded", service: str = None):
        super().__init__(message, service, status_code=429)


class APIAuthenticationError(ExternalServiceError):
    """Exception raised for API authentication failures."""
    
    def __init__(self, message: str = "API authentication failed", service: str = None):
        super().__init__(message, service, status_code=401)


class APIResponseError(ExternalServiceError):
    """Exception raised for invalid API responses."""
    
    def __init__(self, message: str = "Invalid API response", service: str = None, status_code: int = None):
        super().__init__(message, service, status_code)