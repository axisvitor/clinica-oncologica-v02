from __future__ import annotations


class WuzAPIError(Exception):
    """WuzAPI error with response context."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        response: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.response = response


class MediaTooLargeError(WuzAPIError):
    """Raised when media payload exceeds WuzAPI limits."""


class UnsafeMediaUrlError(WuzAPIError):
    """Raised when a media URL is unsafe to fetch."""

    def __init__(self) -> None:
        super().__init__("Blocked media URL", status=None, response=None)


class WuzAPIConnectionError(WuzAPIError):
    """Raised for WuzAPI connection failures."""
