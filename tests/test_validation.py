import math
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from email.utils import formatdate
from urllib.parse import parse_qs, urlsplit

from whollycrypto import Client, Options, Response, ValidationError
from tests.helpers import PROJECT, STORE, TOKEN, FakeTransport, reply


class ValidationTests(unittest.TestCase):
    def test_origins(self):
        bad = (
            "http://api.example.test",
            "https://user:pass@example.com",
            "https://api.example.test/v1",
            "https://api.example.test?",
            "https://api.example.test/#x",
            "https://api.example.test:0",
            "https://api.example.test:99999",
            "https://api.example.test\n",
            "https://foo\\@example.test",
            "https://[::1%25eth0]",
            "https://",
            "file:///tmp/file",
            "https://api..example.test",
            "https://-bad.test",
            "https://api.example.test/%2e",
        )
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Client(value, TOKEN)
        Client("https://api.example.test:8443/", TOKEN).close()
        for value in ("http://localhost:4321", "http://127.0.0.1:4321", "http://[::1]:4321"):
            Client(value, TOKEN, options=Options(allow_insecure_localhost=True)).close()
        with self.assertRaises(ValidationError):
            Client("http://127.0.0.2", TOKEN, options=Options(allow_insecure_localhost=True))

    def test_credentials_and_identifiers(self):
        for token in (None, "", "has space", "x\r\nInjected: yes", "\u2603", "x" * 4097):
            with self.subTest(token=repr(token)), self.assertRaises(ValidationError):
                Client("https://api.example.test", token)
        fake = FakeTransport()
        client = Client("https://api.example.test", TOKEN, transport=fake)
        for value in (None, "my-project", PROJECT + "/../", True, 3):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                client.list_project_wallets(value)
        for key in (None, "", "contains space", "x\r\n", "\u2603", "x" * 129, 1):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                client.create_invoice(PROJECT, STORE, {"amount": "1"}, key)
        self.assertEqual([], fake.requests)
        self.assertEqual(48, len(Client.new_idempotency_key()))
        self.assertNotEqual(Client.new_idempotency_key(), Client.new_idempotency_key())

    def test_money_validation_never_accepts_floats(self):
        client = Client("https://api.example.test", TOKEN, transport=FakeTransport())
        for amount in (
            None,
            True,
            1,
            1.0,
            float("nan"),
            "-1",
            "+1",
            "1e-8",
            "1 ",
            "0." + "1" * 31,
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-0"),
            Decimal("1e99999"),
            Decimal("1e-99999"),
        ):
            with self.subTest(amount=repr(amount)), self.assertRaises(ValidationError):
                client.create_invoice(PROJECT, STORE, {"amount": amount}, "key")
        for field in ("underpayment_tolerance_percent", "exchange_rate_spread_percent"):
            with self.assertRaises(ValidationError):
                client.create_invoice(PROJECT, STORE, {"amount": "1", field: 0.5}, "key")
        with self.assertRaises(ValidationError):
            client.register_custom_token(PROJECT, {"price_usd": 1.0})

    def test_body_limits_bad_json_and_empty_objects(self):
        fake = FakeTransport(reply())
        client = Client("https://api.example.test", TOKEN, transport=fake)
        cycle = {}
        cycle["child"] = cycle
        for metadata in (
            [],
            {"text": "x" * 32768},
            {"float": math.inf},
            {"obj": object()},
            {1: "bad-key"},
            {"bad": "\ud800"},
            cycle,
        ):
            with self.subTest(metadata=type(metadata).__name__), self.assertRaises(ValidationError):
                client.create_invoice(PROJECT, STORE, {"amount": "1", "metadata": metadata}, "key")
        for call in (
            lambda: client.register_token_asset(PROJECT, None),
            lambda: client.update_project_payment_asset(PROJECT, STORE, None),
        ):
            with self.assertRaises(ValidationError):
                call()
        client.create_invoice(
            PROJECT, STORE, {"amount": "1", "metadata": {}, "checkout_appearance": {}}, "key"
        )
        self.assertIn(b'"metadata":{}', fake.requests[0].body)

    def test_options_are_bounded_and_immutable(self):
        for values in (
            {"timeout_seconds": 0},
            {"timeout_seconds": math.nan},
            {"timeout_seconds": 10**400},
            {"max_retries": True},
            {"max_retries": 4},
            {"max_response_bytes": 0},
            {"allow_insecure_localhost": 1},
            {"connect_timeout_seconds": 21},
            {"max_retry_delay_seconds": 61},
            {"ca_file": ""},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Options(**values)
        options = Options()
        with self.assertRaises(FrozenInstanceError):
            options.max_retries = 2

    def test_query_encoding_and_invalid_values(self):
        fake = FakeTransport(reply())
        client = Client("https://api.example.test", TOKEN, transport=fake)
        text = "EUR & BTC/+?\u2713"
        client.list_invoices(PROJECT, {"search": text, "enabled": True, "unused": None})
        query = parse_qs(urlsplit(fake.requests[0].url).query)
        self.assertEqual([text], query["search"])
        self.assertEqual(["true"], query["enabled"])
        self.assertNotIn("unused", query)
        for values in ({"search": []}, {"bad key": "x"}, {"limit": 1.2}, {"search": "\ud800"}, []):
            with self.assertRaises(ValidationError):
                client.list_invoices(PROJECT, values)

    def test_rate_headers_and_http_retry_date(self):
        response = Response(
            429,
            {
                "Retry-After": "19",
                "X-RateLimit-Limit": "120",
                "x-ratelimit-remaining": "0",
                "X-RateLimit-Reset": "1800000060",
            },
            b"",
        )
        self.assertEqual(19, response.retry_after_seconds())
        self.assertEqual({"limit": 120, "remaining": 0, "reset": 1800000060}, response.rate_limit())
        self.assertEqual(
            20,
            Response(429, {"retry-after": formatdate(1800000020, usegmt=True)}, b"").retry_after_seconds(
                1800000000
            ),
        )
        for value in ("tomorrow", "-1", "0\r\n", "9" * 999, "13 Sep 2026 00:00:00 +0000"):
            self.assertIsNone(Response(429, {"retry-after": value}, b"").retry_after_seconds())


if __name__ == "__main__":
    unittest.main()
