"""Wholly Crypto merchant API SDK. No wallet custody or private-service implementation."""

from ._version import __version__
from .checkout import CheckoutClient
from .client import Client
from .exceptions import (
    APIError,
    InvalidResponseError,
    InvalidSignatureError,
    TransportError,
    ValidationError,
    WhollyCryptoError,
)
from .models import Options, Request, Response
from .webhooks import Notification, parse_notification, verify_signature

__all__ = [
    "__version__",
    "Client",
    "CheckoutClient",
    "Options",
    "Request",
    "Response",
    "WhollyCryptoError",
    "ValidationError",
    "TransportError",
    "APIError",
    "InvalidResponseError",
    "InvalidSignatureError",
    "Notification",
    "verify_signature",
    "parse_notification",
]
