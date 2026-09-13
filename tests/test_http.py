import json
import os
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from whollycrypto import APIError, CheckoutClient, Client, InvalidResponseError, Options, TransportError
from whollycrypto.http import HTTPTransport
from tests.helpers import INVOICE, PROJECT, STORE, TOKEN


@contextmanager
def fixture_server(tls=False):
    records = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            self.do_GET()

        def do_GET(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            record = {
                "path": self.path,
                "method": self.command,
                "headers": dict(self.headers),
                "body": body.decode(),
                "connection": self.client_address[1],
            }
            records.append(record)
            kind = parse_qs(urlsplit(self.path).query).get("search", [""])[0]
            status, content_type = 200, "application/json"
            data = json.dumps(
                {
                    "data": {"amount": "0.123456789012345678", "atomic": "999999999999999999999999"},
                    "request": record,
                }
            ).encode()
            headers = {"X-RateLimit-Limit": "120", "X-RateLimit-Remaining": "119"}
            if kind == "redirect":
                status, headers["Location"] = 302, "/trap"
            elif kind == "rate-limit":
                status, headers["Retry-After"] = 429, "19"
            elif kind == "large":
                data = b'{"text":"' + b"x" * 4096 + b'"}'
            elif kind == "html":
                data, content_type = b"<h1>Basic authentication</h1>", "text/html"
            elif kind == "timeout":
                time.sleep(0.4)
            elif kind == "truncated":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "100")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(b'{"data":{}}')
                self.close_connection = True
                return
            elif kind == "duplicate-length":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            elif kind in ("negative-length", "invalid-length", "invalid-transfer-encoding", "both-framings"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Connection", "close")
                if kind == "negative-length":
                    self.send_header("Content-Length", "-1")
                elif kind == "invalid-length":
                    self.send_header("Content-Length", "invalid")
                elif kind == "invalid-transfer-encoding":
                    self.send_header("Transfer-Encoding", "gzip")
                else:
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(data)
                self.close_connection = True
                return
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass

    with tempfile.TemporaryDirectory(prefix="wholly-python-http-") as directory:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server.handle_error = lambda *args: None
        cert = None
        if tls:
            cert, key = Path(directory) / "cert.pem", Path(directory) / "key.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                    "-addext",
                    "subjectAltName=DNS:localhost,IP:127.0.0.1",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.chmod(key, 0o600)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        try:
            yield ("https" if tls else "http") + "://127.0.0.1:" + str(server.server_port), records, cert
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class HTTPTests(unittest.TestCase):
    def test_real_http_connection_reuse_and_auth_separation(self):
        with fixture_server() as (url, records, _):
            options = Options(allow_insecure_localhost=True)
            transport = HTTPTransport()
            try:
                with patch.dict(
                    os.environ,
                    {
                        "HTTP_PROXY": "http://127.0.0.1:1",
                        "HTTPS_PROXY": "http://127.0.0.1:1",
                        "ALL_PROXY": "http://127.0.0.1:1",
                    },
                ):
                    client = Client(url, TOKEN, options=options, transport=transport)
                    result = client.create_invoice(
                        PROJECT, STORE, {"amount": "25.00", "metadata": {}}, "saved-key"
                    )
                    self.assertEqual("Bearer " + TOKEN, result["request"]["headers"]["Authorization"])
                    self.assertEqual("saved-key", result["request"]["headers"]["Idempotency-Key"])
                    self.assertEqual("25.00", json.loads(result["request"]["body"])["amount"])
                    self.assertEqual(119, client.last_response.rate_limit()["remaining"])
                    client.health()
                    CheckoutClient(url, options=options, transport=transport).get_invoice(INVOICE)
                self.assertEqual(1, len({entry["connection"] for entry in records}))
                for entry in records[1:]:
                    self.assertNotIn("Authorization", entry["headers"])
                    self.assertEqual("", entry["body"])
            finally:
                transport.close()

    def test_redirects_html_quota_and_size_limits(self):
        with fixture_server() as (url, records, _):
            with Client(url, TOKEN, options=Options(allow_insecure_localhost=True)) as client:
                with self.assertRaises(APIError) as caught:
                    client.list_invoices(PROJECT, {"search": "redirect"})
                self.assertEqual("redirect_not_followed", caught.exception.error_code)
                self.assertFalse(any(entry["path"] == "/trap" for entry in records))
                with self.assertRaises(InvalidResponseError):
                    client.list_invoices(PROJECT, {"search": "html"})
                with self.assertRaises(APIError) as caught:
                    client.list_invoices(PROJECT, {"search": "rate-limit"})
                self.assertEqual(19, caught.exception.retry_after)
            with Client(
                url, TOKEN, options=Options(allow_insecure_localhost=True, max_response_bytes=1024)
            ) as limited:
                with self.assertRaises(TransportError):
                    limited.list_invoices(PROJECT, {"search": "large"})

    def test_timeout_truncation_and_ambiguous_framing(self):
        with fixture_server() as (url, _, _):
            options = Options(
                allow_insecure_localhost=True, timeout_seconds=0.15, connect_timeout_seconds=0.1
            )
            with Client(url, TOKEN, options=options) as client:
                with self.assertRaises(TransportError) as caught:
                    client.list_invoices(PROJECT, {"search": "timeout"})
                self.assertTrue(caught.exception.retryable)
            with Client(url, TOKEN, options=Options(allow_insecure_localhost=True)) as client:
                for value in (
                    "truncated",
                    "duplicate-length",
                    "negative-length",
                    "invalid-length",
                    "invalid-transfer-encoding",
                    "both-framings",
                ):
                    with self.subTest(value=value), self.assertRaises(TransportError):
                        client.list_invoices(PROJECT, {"search": value})

    def test_tls_requires_trust_even_for_localhost(self):
        with fixture_server(tls=True) as (url, _, cert):
            with Client(url, TOKEN, options=Options(allow_insecure_localhost=True)) as client:
                with self.assertRaises(TransportError) as caught:
                    client.health()
                self.assertFalse(caught.exception.retryable)
                self.assertIn("certificate verification", str(caught.exception))
            with Client(url, TOKEN, options=Options(ca_file=str(cert))) as client:
                self.assertIn("data", client.health())


if __name__ == "__main__":
    unittest.main()
