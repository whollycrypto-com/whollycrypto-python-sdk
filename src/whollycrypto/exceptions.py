"""Safe exception messages; response bodies are explicit opt-in access."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Response


class WhollyCryptoError(Exception):
    """Base SDK error."""


class ValidationError(WhollyCryptoError, ValueError):
    """Invalid local configuration or request. No HTTP request was sent."""


class TransportError(WhollyCryptoError):
    """A network failure; it does not prove an invoice was not created."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class InvalidResponseError(WhollyCryptoError):
    """The API did not return the expected JSON response shape."""


class InvalidSignatureError(WhollyCryptoError):
    """An IPN/webhook signature, clock window or payload is invalid."""


class APIError(WhollyCryptoError):
    """HTTP failure. api_message/response may contain private customer details."""

    def __init__(self, status_code: int, error_code: str, api_message: str | None, response: Response):
        super().__init__(f"Wholly Crypto API request failed (HTTP {status_code}, {error_code}).")
        self.status_code = status_code
        self.error_code = error_code
        self.api_message = api_message
        self.response = response

    @property
    def retry_after(self) -> int | None:
        return self.response.retry_after_seconds()
