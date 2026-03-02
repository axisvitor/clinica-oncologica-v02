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


class WuzAPIConnectionError(WuzAPIError):
    """Raised for WuzAPI connection failures."""
