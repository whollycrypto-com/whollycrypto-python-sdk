"""IPN/webhook exact-byte authentication. Event/delivery headers are NOT signed."""

from __future__ import annotations

import hmac
import re
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from ._validation import decode_json, uuid_path
from .exceptions import InvalidSignatureError, ValidationError

MAX_BODY_BYTES = 262_144


def verify_signature(
    raw_body: bytes,
    signature: str | None,
    signing_secret: str | bytes,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    """Verify raw bytes before JSON parsing. Invalid local configuration raises ValidationError."""
    if not isinstance(raw_body, bytes):
        raise ValidationError("Pass the exact raw HTTP body as bytes, before decoding or parsing JSON.")
    if type(tolerance_seconds) is not int or not 0 <= tolerance_seconds <= 86_400:
        raise ValidationError("Clock tolerance must be an integer from 0 to 86400 seconds.")
    if now is not None and (type(now) is not int or now < 0):
        raise ValidationError("now must be a nonnegative Unix timestamp.")
    if not isinstance(signing_secret, (str, bytes)) or not signing_secret:
        raise ValidationError("Configure a nonempty IPN/webhook signing secret, not an API token.")
    try:
        secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
    except UnicodeError:
        raise ValidationError("Signing secret contains invalid Unicode.") from None
    if len(raw_body) > MAX_BODY_BYTES or not isinstance(signature, str):
        return False
    match = re.fullmatch(r"t=(0|[1-9][0-9]{0,11}),v1=([0-9a-f]{64})", signature)
    if match is None:
        return False
    timestamp = int(match[1])
    if abs((int(time.time()) if now is None else now) - timestamp) > tolerance_seconds:
        return False
    digest = hmac.digest(secret, match[1].encode("ascii") + b"." + raw_body, "sha256").hex()
    return hmac.compare_digest(digest, match[2])


def _freeze(value: Any, depth: int = 0) -> Any:
    if depth > 32:
        raise InvalidSignatureError("Signed notification nesting is too deep.")
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child, depth + 1) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child, depth + 1) for child in value)
    return value


@dataclass(frozen=True, slots=True)
class Notification:
    event_id: str
    delivery_id: str
    payload: Mapping[str, Any] = field(repr=False)

    @property
    def invoice_id(self) -> str:
        """The signed public invoice UUID, suitable for Client.get_invoice()."""
        return self.payload["invoice_id"]

    @property
    def status(self) -> str:
        return self.payload["status"]

    @property
    def sequence(self) -> int:
        return self.payload["sequence"]


def parse_notification(
    raw_body: bytes,
    headers: Mapping[str, str] | Iterable[tuple[str, str]],
    signing_secret: str | bytes,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> Notification:
    """Verify first, then decode. Persist invoice+sequence replay protection before acknowledging."""
    normalized = {}
    items = headers.items() if isinstance(headers, Mapping) else headers
    try:
        for index, item in enumerate(items):
            if index >= 128 or not isinstance(item, (tuple, list)) or len(item) != 2:
                raise InvalidSignatureError("Notification has invalid headers.")
            name, value = item
            if not isinstance(name, str) or not isinstance(value, str):
                raise InvalidSignatureError("Notification has invalid headers.")
            name = name.lower()
            if name in ("wholly-signature", "wholly-event-id", "wholly-delivery-id"):
                if name in normalized:
                    raise InvalidSignatureError("Duplicate notification security header.")
                normalized[name] = value
    except (TypeError, ValueError):
        raise InvalidSignatureError("Notification has invalid headers.") from None
    if not verify_signature(
        raw_body,
        normalized.get("wholly-signature"),
        signing_secret,
        tolerance_seconds=tolerance_seconds,
        now=now,
    ):
        raise InvalidSignatureError("Invalid or expired notification signature.")
    try:
        payload = decode_json(raw_body)
        event_id = uuid_path(normalized.get("wholly-event-id"))
        delivery_id = uuid_path(normalized.get("wholly-delivery-id"))
        if (
            not isinstance(payload, dict)
            or type(payload.get("sequence")) is not int
            or not 1 <= payload["sequence"] <= 9_223_372_036_854_775_807
            or payload.get("status")
            not in ("new", "processing", "settled", "expired", "invalid", "cancelled")
        ):
            raise ValueError
        uuid_path(payload.get("invoice_id"))
        return Notification(event_id, delivery_id, _freeze(payload))
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidSignatureError("Signed notification has invalid identifiers or payload.") from None
