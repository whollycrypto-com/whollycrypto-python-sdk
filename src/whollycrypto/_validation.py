from __future__ import annotations

import ipaddress
import json
import math
import re
from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import quote, urlencode, urlsplit
from uuid import UUID

from .exceptions import ValidationError
from .models import Options


def origin(value: str, options: Options) -> str:
    if not isinstance(value, str) or not value or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValidationError("Use an absolute HTTPS origin without whitespace or control characters.")
    if any(c in value for c in ("\\", "?", "#")):
        raise ValidationError("API origins must not contain a query, fragment or backslash.")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").encode("idna").decode("ascii").lower()
        port = parts.port
        if not host or "%" in host or parts.username is not None or parts.password is not None:
            raise ValueError
        if parts.path not in ("", "/") or (port is not None and not 1 <= port <= 65535):
            raise ValueError
        if ":" in host:
            ipaddress.IPv6Address(host)
            authority = "[" + host + "]"
        else:
            if len(host) > 253 or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in host.rstrip(".").split(".")
            ):
                raise ValueError
            authority = host
        local = host in ("localhost", "127.0.0.1", "::1")
        if parts.scheme != "https" and not (
            parts.scheme == "http" and local and options.allow_insecure_localhost
        ):
            raise ValueError
        return parts.scheme + "://" + authority + (":" + str(port) if port is not None else "")
    except (ValueError, UnicodeError):
        raise ValidationError(
            "Use an HTTPS origin such as https://api.example.com, without /v1 or credentials. HTTP is only allowed for explicitly enabled loopback tests."
        ) from None


def uuid_path(value: object) -> str:
    text = str(value) if isinstance(value, UUID) else value
    if not isinstance(text, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", text
    ):
        raise ValidationError("Expected an API UUID, not a project/store identifier or order ID.")
    return text.lower()


def decimal_string(value: Any, field: str) -> str:
    if isinstance(value, Decimal):
        # Bound before formatting to prevent huge exponent allocations.
        exponent = value.as_tuple().exponent
        if (
            not value.is_finite()
            or value.is_signed()
            or value.adjusted() > 47
            or not isinstance(exponent, int)
            or exponent < -30
        ):
            raise ValidationError(field + " must be an unsigned decimal string or a finite Decimal.")
        value = format(value, "f")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,48}(?:\.[0-9]{1,30})?", value):
        raise ValidationError(field + " must be a plain unsigned decimal string or Decimal, never a float.")
    return value


def canonical(value: Any, depth: int = 0) -> Any:
    if depth > 32:
        raise ValidationError("JSON request nesting is too deep.")
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValidationError("JSON object keys must be strings.")
        return {key: canonical(value[key], depth + 1) for key in sorted(value)}
    if isinstance(value, list):
        return [canonical(child, depth + 1) for child in value]
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValidationError(
        "Use JSON scalars, objects and lists; non-finite numbers and custom objects are not supported."
    )


def encode_body(data: Mapping[str, Any]) -> bytes:
    if not isinstance(data, Mapping):
        raise ValidationError("The request body must be a JSON object.")
    try:
        encoded = json.dumps(
            canonical(data), ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise ValidationError("Request contains an invalid JSON value, nesting or Unicode string.") from None
    if len(encoded) > 32_768:
        raise ValidationError("Merchant JSON body exceeds the 32 KiB limit.")
    return encoded


def query_string(query: Mapping[str, Any] | None) -> str:
    if query is None:
        return ""
    if not isinstance(query, Mapping):
        raise ValidationError("Query parameters must be a mapping.")
    pairs = []
    for key, value in query.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z_]+", key):
            raise ValidationError("Query parameters must have named scalar values.")
        if value is None:
            continue
        if type(value) not in (str, int, bool):
            raise ValidationError("Query values must be strings, integers, booleans or None.")
        pairs.append((key, str(value).lower() if type(value) is bool else str(value)))
    try:
        return urlencode(pairs, quote_via=quote, safe="")
    except UnicodeError:
        raise ValidationError("Query contains an invalid Unicode string.") from None


def decode_json(raw: bytes) -> Any:
    def reject_constant(value: str):
        raise ValueError("Non-finite JSON number")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8"),
        parse_float=Decimal,
        parse_constant=reject_constant,
        object_pairs_hook=unique_object,
    )
