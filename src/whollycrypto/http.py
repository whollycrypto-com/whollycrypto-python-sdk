"""Standard-library HTTPS transport with connection reuse and no implicit credentials."""

from __future__ import annotations

import http.client
import re
import socket
import ssl
import threading
import time
from typing import NoReturn, Protocol, SupportsIndex
from urllib.parse import urlsplit

from .exceptions import TransportError
from .models import Options, Request, Response


class Transport(Protocol):
    """Custom transports receive credentials. Only inject trusted implementations."""

    def send(self, request: Request, options: Options) -> Response: ...

    def close(self) -> None: ...


class HTTPTransport:
    """One reusable connection; no proxy discovery, redirects, cookies or .netrc."""

    def __init__(self) -> None:
        self._connection: http.client.HTTPConnection | None = None
        self._key: tuple | None = None
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return "HTTPTransport()"

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError("HTTP transports must not be pickled.")

    def _disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._key = None

    def close(self) -> None:
        with self._lock:
            self._disconnect()

    def send(self, request: Request, options: Options) -> Response:
        started = time.monotonic()
        if not self._lock.acquire(timeout=options.timeout_seconds):
            raise TransportError("HTTP transport is busy; use one client per worker.", retryable=True)
        response = None
        try:
            parts = urlsplit(request.url)
            hostname = parts.hostname
            if not hostname or parts.username is not None or parts.password is not None or parts.fragment:
                raise TransportError("Invalid HTTP request origin.")
            local_http = (
                parts.scheme == "http"
                and options.allow_insecure_localhost
                and parts.hostname in ("localhost", "127.0.0.1", "::1")
            )
            if parts.scheme != "https" and not local_http:
                raise TransportError("HTTPS is required.")
            key = (parts.scheme, parts.hostname, parts.port, options.ca_file)
            if self._key != key:
                self._disconnect()
                if parts.scheme == "https":
                    context = ssl.create_default_context(cafile=options.ca_file)
                    self._connection = http.client.HTTPSConnection(
                        hostname,
                        parts.port,
                        timeout=options.connect_timeout_seconds,
                        context=context,
                    )
                else:
                    self._connection = http.client.HTTPConnection(
                        hostname,
                        parts.port,
                        timeout=options.connect_timeout_seconds,
                    )
                self._connection.set_debuglevel(0)
                self._key = key
            connection = self._connection
            if connection is None:
                raise TransportError("HTTP connection could not be initialized.")

            def remaining() -> float:
                seconds = options.timeout_seconds - (time.monotonic() - started)
                if seconds <= 0:
                    raise TimeoutError
                return seconds

            if connection.sock is None:
                connection.timeout = min(options.connect_timeout_seconds, remaining())
                connection.connect()
            connection.sock.settimeout(remaining())
            target = (parts.path or "/") + ("?" + parts.query if parts.query else "")
            connection.request(request.method, target, body=request.body, headers=dict(request.headers))
            connection.sock.settimeout(remaining())
            response = connection.getresponse()
            pairs = response.getheaders()
            if sum(len(k) + len(v) + 4 for k, v in pairs) > 32_768:
                raise TransportError("Response headers exceeded the 32 KiB limit.")
            headers: dict[str, str] = {}
            for name, value in pairs:
                name = name.lower()
                # Repeated security/framing headers must not be silently overwritten.
                if name in headers and name in (
                    "content-length",
                    "content-type",
                    "retry-after",
                    "transfer-encoding",
                ):
                    raise TransportError("Response has ambiguous framing or retry headers.")
                headers[name] = value
            if "content-length" in headers and "transfer-encoding" in headers:
                raise TransportError("Response has ambiguous framing headers.")
            if "content-length" in headers and not re.fullmatch(r"[0-9]{1,20}", headers["content-length"]):
                raise TransportError("Response has an invalid content length.")
            if "transfer-encoding" in headers and headers["transfer-encoding"].lower() != "chunked":
                raise TransportError("Response has an unsupported transfer encoding.")
            if response.length is not None and response.length > options.max_response_bytes:
                raise TransportError("Response exceeded the configured size limit.")
            body = bytearray()
            while True:
                # read1 avoids waiting for an entire large block from a slow peer.
                # For close-delimited responses, http.client may already own the socket.
                seconds = remaining()
                if connection.sock is not None:
                    connection.sock.settimeout(seconds)
                chunk = response.read1(min(65_536, options.max_response_bytes + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > options.max_response_bytes:
                    raise TransportError("Response exceeded the configured size limit.")
            if response.length not in (None, 0):
                raise TransportError("HTTP response body ended early.", retryable=True)
            return Response(response.status, headers, bytes(body))
        except ssl.SSLCertVerificationError:
            self._disconnect()
            raise TransportError(
                "HTTPS certificate verification failed. Check the hostname, certificate and trusted CA bundle."
            ) from None
        except ssl.SSLError:
            self._disconnect()
            raise TransportError("The HTTPS handshake or secure connection failed.") from None
        except (TimeoutError, ConnectionError, socket.gaierror, http.client.IncompleteRead):
            self._disconnect()
            raise TransportError(
                "Wholly Crypto connection failed or timed out. Check HTTPS, DNS and connectivity.",
                retryable=True,
            ) from None
        except (OSError, http.client.HTTPException, ValueError):
            self._disconnect()
            raise TransportError(
                "Wholly Crypto connection or HTTP protocol failed. Check server connectivity and TLS configuration."
            ) from None
        except TransportError:
            self._disconnect()
            raise
        finally:
            if response is not None:
                response.close()
            self._lock.release()
