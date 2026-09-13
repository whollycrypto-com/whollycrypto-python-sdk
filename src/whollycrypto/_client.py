from __future__ import annotations

import random
import re
import time
from typing import Any, Mapping, NoReturn, SupportsIndex

from . import _validation as validate
from ._version import __version__
from .exceptions import APIError, InvalidResponseError, TransportError, ValidationError
from .http import HTTPTransport, Transport
from .models import Options, Request, Response


class JSONClient:
    def __init__(
        self, base_url: str, token: str | None, options: Options | None, transport: Transport | None
    ):
        self.options = options if options is not None else Options()
        if not isinstance(self.options, Options):
            raise ValidationError("options must be an Options instance.")
        self.origin = validate.origin(base_url, self.options)
        if token is not None and (
            not isinstance(token, str) or not re.fullmatch(r"[\x21-\x7e]{1,4096}", token)
        ):
            raise ValidationError("API token must be nonempty visible ASCII without spaces or newlines.")
        self._token = token
        self._transport = transport if transport is not None else HTTPTransport()
        self._owns_transport = transport is None
        self._closed = False
        self.last_response: Response | None = None

    def __repr__(self) -> str:
        return f"JSONClient(authenticated={self._token is not None}, closed={self._closed})"

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError("API clients containing credentials must not be pickled.")

    def close(self) -> None:
        if not self._closed and self._owns_transport:
            self._transport.close()
        self._closed = True

    def url(self, path: str, query: Mapping[str, Any] | None = None) -> str:
        if not re.fullmatch(r"/[a-zA-Z0-9/_-]*", path) or path.startswith("//"):
            raise ValidationError("Invalid relative API path.")
        encoded = validate.query_string(query)
        return self.origin + path + ("?" + encoded if encoded else "")

    def request(
        self,
        method: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        *,
        data: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        self.last_response = None
        if self._closed:
            raise ValidationError("This client is closed; create a new client.")
        if method not in ("GET", "POST", "PUT"):
            raise ValidationError("Unsupported HTTP method.")
        if method in ("POST", "PUT") and not isinstance(data, Mapping):
            raise ValidationError("Write requests require a JSON object body.")
        headers = {"Accept": "application/json", "User-Agent": "WhollyCrypto-Python/" + __version__}
        if authenticated:
            if self._token is None:
                raise ValidationError("This operation requires a merchant API token.")
            headers["Authorization"] = "Bearer " + self._token
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not re.fullmatch(
                r"[\x21-\x7e]{1,128}", idempotency_key
            ):
                raise ValidationError(
                    "Idempotency key must contain 1–128 visible ASCII characters without spaces."
                )
            headers["Idempotency-Key"] = idempotency_key
        body = None if data is None else validate.encode_body(data)
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(method, self.url(path, query), headers, body)
        can_retry = method == "GET" or (method == "POST" and idempotency_key is not None)
        for attempt in range(self.options.max_retries + 1):
            self.last_response = None
            try:
                response = self._transport.send(request, self.options)
            except TransportError as error:
                if not can_retry or not error.retryable or attempt >= self.options.max_retries:
                    raise
                self._pause(attempt, None)
                continue
            if (
                not isinstance(response, Response)
                or type(response.status_code) is not int
                or not 100 <= response.status_code <= 599
            ):
                raise InvalidResponseError("Transport did not return a valid HTTP Response.")
            self.last_response = response
            wait = response.retry_after_seconds()
            if (
                can_retry
                and attempt < self.options.max_retries
                and response.status_code in (429, 502, 503, 504)
                and (response.header("retry-after") is None or wait is not None)
                and (wait or 0) <= self.options.max_retry_delay_seconds
            ):
                self._pause(attempt, wait)
                continue
            return self._decode(response)
        raise AssertionError("Unreachable retry state")

    def _pause(self, attempt: int, wait: int | None) -> None:
        delay = min(self.options.max_retry_delay_seconds, 2**attempt) if wait is None else wait
        time.sleep(delay + random.uniform(0, 0.1))

    def _decode(self, response: Response) -> dict[str, Any]:
        kind = (response.header("content-type") or "").split(";", 1)[0].strip().lower()
        is_json = kind == "application/json" or re.fullmatch(r"application/[a-z0-9.+-]+\+json", kind)
        data = None
        if is_json and len(response.body) <= self.options.max_response_bytes:
            try:
                candidate = validate.decode_json(response.body)
                if isinstance(candidate, dict):
                    data = candidate
            except (ValueError, UnicodeError, RecursionError):
                pass
        if not 200 <= response.status_code < 300:
            error = data.get("error", {}) if data is not None else {}
            error = error if isinstance(error, dict) else {}
            code = error.get("code")
            if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,100}", code):
                code = "redirect_not_followed" if 300 <= response.status_code < 400 else "http_error"
            if self._token and self._token in code:
                code = "http_error"
            message = error.get("message")
            message = message[:4096] if isinstance(message, str) else None
            raise APIError(response.status_code, code, message, response)
        if data is None:
            raise InvalidResponseError(
                "Expected a bounded JSON object from the API. Check the API hostname; HTML login/error pages are not API responses."
            )
        return data
