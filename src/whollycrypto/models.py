"""Immutable request/options/response values. Repr never includes credentials or bodies."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import format_datetime, parsedate_to_datetime
from types import MappingProxyType
from typing import Mapping, NoReturn, SupportsIndex

from .exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Options:
    timeout_seconds: float = 20
    connect_timeout_seconds: float = 5
    max_retries: int = 0
    max_retry_delay_seconds: float = 60
    max_response_bytes: int = 8_388_608
    allow_insecure_localhost: bool = False
    ca_file: str | None = None

    def __post_init__(self) -> None:
        for value in (self.timeout_seconds, self.connect_timeout_seconds, self.max_retry_delay_seconds):
            if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
                raise ValidationError("Timeout and retry delays must be finite numbers.")
        if not (0 < self.connect_timeout_seconds <= self.timeout_seconds <= 120):
            raise ValidationError("Connect timeout must be positive and no greater than timeout (max 120s).")
        if not (0 <= self.max_retry_delay_seconds <= 60):
            raise ValidationError("Maximum retry delay must be between 0 and 60 seconds.")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 3:
            raise ValidationError("max_retries must be an integer between 0 and 3.")
        if type(self.max_response_bytes) is not int or not 1024 <= self.max_response_bytes <= 67_108_864:
            raise ValidationError("Response-size limit must be between 1 KiB and 64 MiB.")
        if type(self.allow_insecure_localhost) is not bool:
            raise ValidationError("allow_insecure_localhost must be a boolean.")
        if self.ca_file is not None and (not isinstance(self.ca_file, str) or not self.ca_file):
            raise ValidationError("ca_file must be a trusted CA bundle path or None.")


@dataclass(frozen=True, slots=True, repr=False)
class Request:
    """Trusted custom transports can access headers/body; never log or pickle them."""

    method: str
    url: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))
        if self.body is not None and not isinstance(self.body, bytes):
            raise ValidationError("Request bodies must be immutable bytes.")

    def __repr__(self) -> str:
        return f"Request(method={self.method!r}, body_bytes={len(self.body or b'')})"

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError("Requests containing credentials must not be pickled.")


@dataclass(frozen=True, slots=True, repr=False)
class Response:
    status_code: int
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType({k.lower(): v for k, v in self.headers.items()}))
        if not isinstance(self.body, bytes):
            raise ValidationError("Response bodies must be bytes.")

    def __repr__(self) -> str:
        return f"Response(status_code={self.status_code}, body_bytes={len(self.body)})"

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def retry_after_seconds(self, now: int | None = None) -> int | None:
        value = self.header("retry-after")
        if value is None:
            return None
        if re.fullmatch(r"[0-9]{1,9}", value):
            return int(value)
        # Accept HTTP date forms, never relative expressions such as "tomorrow".
        if len(value) > 64 or "\r" in value or "\n" in value:
            return None
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo != timezone.utc or format_datetime(date, usegmt=True) != value:
                return None
            return max(0, math.ceil(date.timestamp() - (time.time() if now is None else now)))
        except (TypeError, ValueError, OverflowError):
            return None

    def rate_limit(self) -> dict[str, int | None]:
        return {
            field: int(value) if value is not None and re.fullmatch(r"[0-9]{1,10}", value) else None
            for field in ("limit", "remaining", "reset")
            for value in (self.header("x-ratelimit-" + field),)
        }
