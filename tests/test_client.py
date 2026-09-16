import json
import pickle
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from whollycrypto import (
    APIError,
    CheckoutClient,
    Client,
    InvalidResponseError,
    Options,
    Response,
    TransportError,
    ValidationError,
)
from tests.helpers import ASSET, INVOICE, PROJECT, STORE, TOKEN, FakeTransport, invoke, reply


class ClientTests(unittest.TestCase):
    def test_payment_readiness_errors_are_actionable_and_safe(self):
        issue = {'chain_slug':'tron','asset_ticker':TOKEN,'reason_code':'scanner_provider_quorum','usable_independent_providers':1,'message':TOKEN}
        error = APIError(400, 'invalid_payment_request', TOKEN, reply({'error':{'details':{'payment_methods':[issue, issue]}}}, 400))
        self.assertIn('TRON: 1 of 2 independent scanner providers', str(error))
        self.assertEqual(str(error).count('TRON:'), 1)
        self.assertNotIn(TOKEN, repr(error))
        self.assertEqual(error.payment_method_issues, [issue, issue])
        for issues in [None, 1, 'bad', [{'reason_code':[]}], [{'chain_slug':TOKEN,'reason_code':'rate_unavailable','message':TOKEN}], [{'chain_slug':'tron','reason_code':'scanner_provider_quorum','usable_independent_providers':TOKEN}]]:
            error = APIError(400, 'invalid_payment_request', TOKEN, reply({'error':{'details':{'payment_methods':issues}}}, 400))
            self.assertNotIn(TOKEN, str(error))
        self.assertEqual(APIError(400,'http_error',None,Response(400,{},b'not JSON')).details,{})

    def test_all_18_public_contracts(self):
        catalog = json.loads((Path(__file__).parent / "fixtures/api-v1.json").read_text())
        self.assertEqual(18, len(catalog["endpoints"]))
        for endpoint in catalog["endpoints"]:
            with self.subTest(endpoint=endpoint["id"]):
                transport = FakeTransport(reply(endpoint["response"]))
                client = Client("https://api.example.test/", TOKEN, transport=transport)
                result = invoke(client, endpoint["id"], endpoint["body"])
                self.assertEqual(endpoint["response"], result)
                self.assertEqual(1, len(transport.requests))
                request = transport.requests[0]
                self.assertEqual(endpoint["method"], request.method)
                path = endpoint["path"].format(
                    project_id=PROJECT, store_id=STORE, invoice_id=INVOICE, asset_id=ASSET
                )
                self.assertEqual(path, urlsplit(request.url).path)
                self.assertEqual(
                    None if endpoint["access"] == "public" else "Bearer " + TOKEN,
                    request.headers.get("Authorization"),
                )
                self.assertEqual(endpoint["body"], None if request.body is None else json.loads(request.body))
                if endpoint["id"] == "create-invoice":
                    self.assertEqual("persisted-order-1042", request.headers["Idempotency-Key"])

    def test_exact_money_decimal_and_canonical_bytes(self):
        transport = FakeTransport(
            reply(),
            reply(),
            Response(
                200,
                {"Content-Type": "application/json"},
                b'{"large":99999999999999999999999999999,"rate":0.1234567890123456789012345}',
            ),
        )
        client = Client("https://api.example.test", TOKEN, transport=transport)
        payload = {
            "amount": Decimal("49.90"),
            "currency": "EUR",
            "metadata": {"z": "\u2713", "a": []},
            "checkout_appearance": {},
        }
        client.create_invoice(PROJECT, STORE, payload, "saved-key")
        self.assertIsInstance(payload["amount"], Decimal)  # Never mutate the caller's object.
        self.assertEqual(
            b'{"amount":"49.90","checkout_appearance":{},"currency":"EUR","metadata":{"a":[],"z":"\xe2\x9c\x93"}}',
            transport.requests[0].body,
        )
        client.register_custom_token(PROJECT, {"price_usd": Decimal("1E-8")})
        self.assertEqual({"price_usd": "0.00000001"}, json.loads(transport.requests[1].body))
        result = client.health()
        self.assertEqual(99999999999999999999999999999, result["large"])
        self.assertEqual(Decimal("0.1234567890123456789012345"), result["rate"])

    def test_bounded_opt_in_invoice_retries_preserve_identity(self):
        transport = FakeTransport(reply(status=429, headers={"Retry-After": "0"}), reply())
        client = Client(
            "https://api.example.test", TOKEN, options=Options(max_retries=1), transport=transport
        )
        with patch("whollycrypto._client.time.sleep") as sleep:
            client.create_invoice(PROJECT, STORE, {"amount": "1.00"}, "persisted-key")
        self.assertEqual(2, len(transport.requests))
        self.assertIs(transport.requests[0], transport.requests[1])
        sleep.assert_called_once()

    def test_retries_off_by_default_and_other_writes_never_retry(self):
        transport = FakeTransport(reply(status=503), reply())
        with self.assertRaises(APIError):
            Client("https://api.example.test", TOKEN, transport=transport).health()
        self.assertEqual(1, len(transport.requests))
        writes = (
            "register-token-asset",
            "register-custom-token",
            "update-project-payment-asset",
            "update-store-payment-assets",
            "update-store-confirmation-policy",
        )
        for endpoint in writes:
            with self.subTest(endpoint=endpoint):
                fake = FakeTransport(reply(status=503), reply())
                client = Client(
                    "https://api.example.test", TOKEN, options=Options(max_retries=3), transport=fake
                )
                with self.assertRaises(APIError):
                    invoke(client, endpoint, {"assets": [], "enabled": True})
                self.assertEqual(1, len(fake.requests))

    def test_transport_retries_only_transient_failures(self):
        for retryable, expected in ((True, 2), (False, 1)):
            fake = FakeTransport(TransportError("fixture", retryable=retryable), reply())
            client = Client("https://api.example.test", TOKEN, options=Options(max_retries=1), transport=fake)
            with patch("whollycrypto._client.time.sleep"):
                if retryable:
                    client.health()
                else:
                    with self.assertRaises(TransportError):
                        client.health()
            self.assertEqual(expected, len(fake.requests))

    def test_bad_or_long_retry_after_is_not_retried_early(self):
        for value in ("61", "tomorrow", "-1"):
            transport = FakeTransport(reply(status=429, headers={"Retry-After": value}), reply())
            client = Client(
                "https://api.example.test", TOKEN, options=Options(max_retries=3), transport=transport
            )
            with patch("whollycrypto._client.time.sleep") as sleep, self.assertRaises(APIError):
                client.health()
            sleep.assert_not_called()
            self.assertEqual(1, len(transport.requests))

    def test_api_errors_redact_messages_and_preserve_status(self):
        fake = FakeTransport(
            reply(
                {"error": {"code": "rate_limit_exceeded", "message": "private " + TOKEN}},
                429,
                {"Retry-After": "19"},
            )
        )
        client = Client("https://api.example.test", TOKEN, transport=fake)
        with self.assertRaises(APIError) as caught:
            client.list_project_wallets(PROJECT)
        error = caught.exception
        self.assertEqual(429, error.status_code)
        self.assertEqual(19, error.retry_after)
        self.assertEqual("rate_limit_exceeded", error.error_code)
        self.assertIn(TOKEN, error.api_message)
        self.assertNotIn(TOKEN, str(error))
        self.assertNotIn(TOKEN, repr(error))
        self.assertIs(client.last_response, error.response)
        fake = FakeTransport(reply({"error": {"code": TOKEN}}, 400))
        with self.assertRaises(APIError) as caught:
            Client("https://api.example.test", TOKEN, transport=fake).health()
        self.assertEqual("http_error", caught.exception.error_code)

    def test_invalid_json_and_html_keep_http_errors(self):
        for raw in (b"[]", b"null", b"{", b'{"x":NaN}', b'{"x":1,"x":2}', b"\xff", b'{"x":Infinity}'):
            with self.subTest(raw=raw):
                fake = FakeTransport(Response(200, {"content-type": "application/json"}, raw))
                with self.assertRaises(InvalidResponseError):
                    Client("https://api.example.test", TOKEN, transport=fake).health()
        for status in (302, 403, 502):
            fake = FakeTransport(Response(status, {"content-type": "text/html"}, b"<h1>proxy</h1>"))
            with self.assertRaises(APIError) as caught:
                Client("https://api.example.test", TOKEN, transport=fake).health()
            self.assertEqual(status, caught.exception.status_code)

    def test_pagination_lazy_and_bounded(self):
        fake = FakeTransport(
            reply(
                {"data": [{"invoice_id": INVOICE}], "pagination": {"offset": 0, "limit": 1, "has_more": True}}
            ),
            reply(
                {"data": [{"invoice_id": ASSET}], "pagination": {"offset": 1, "limit": 1, "has_more": False}}
            ),
        )
        client = Client("https://api.example.test", TOKEN, transport=fake)
        iterator = client.iter_invoices(PROJECT, {"limit": 1, "status": "settled"})
        self.assertEqual(0, len(fake.requests))
        self.assertEqual([INVOICE, ASSET], [row["invoice_id"] for row in iterator])
        self.assertEqual(["1"], parse_qs(urlsplit(fake.requests[1].url).query)["offset"])
        for pagination in (
            {"offset": 0, "limit": 50, "has_more": True},
            {"offset": False, "limit": 50, "has_more": False},
            {},
        ):
            fake = FakeTransport(reply({"data": [], "pagination": pagination}))
            with self.assertRaises(InvalidResponseError):
                list(Client("https://api.example.test", TOKEN, transport=fake).iter_invoices(PROJECT))

    def test_checkout_and_public_reads_never_send_auth(self):
        fake = FakeTransport(reply(), reply(), reply(), reply())
        checkout = CheckoutClient("https://pay.example.test", transport=fake)
        checkout.get_invoice(INVOICE)
        checkout.get_preview(PROJECT, STORE)
        client = Client("https://api.example.test", TOKEN, transport=fake)
        client.service_info()
        client.health()
        self.assertTrue(all("Authorization" not in r.headers for r in fake.requests))
        self.assertEqual("https://pay.example.test/invoice/" + INVOICE, checkout.invoice_url(UUID(INVOICE)))
        self.assertIn("state=paid", checkout.preview_url(PROJECT, STORE, "paid"))
        with self.assertRaises(ValidationError):
            checkout.preview_url(PROJECT, state="settled")

    def test_request_debugging_and_pickle_redaction(self):
        fake = FakeTransport(reply())
        client = Client("https://api.example.test", TOKEN, transport=fake)
        client.get_invoice(PROJECT, INVOICE)
        for value in (client, client._http, fake.requests[0]):
            self.assertNotIn(TOKEN, repr(value))
            with self.assertRaises(TypeError):
                pickle.dumps(value)
        with self.assertRaises(TypeError):
            fake.requests[0].headers["Authorization"] = "changed"
        client.close()
        self.assertFalse(fake.closed)  # Caller owns injected/shared transports.
        with self.assertRaises(ValidationError):
            client.health()

    def test_store_selection_is_replaced_and_empty_is_explicit(self):
        fake = FakeTransport(reply())
        client = Client("https://api.example.test", TOKEN, transport=fake)
        client.update_store_payment_assets(PROJECT, STORE, [])
        self.assertEqual(b'{"assets":[]}', fake.requests[0].body)
        with self.assertRaises(ValidationError):
            client.update_store_payment_assets(PROJECT, STORE, {"assets": []})


if __name__ == "__main__":
    unittest.main()
