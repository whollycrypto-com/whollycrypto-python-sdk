import hashlib
import hmac
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from tests.helpers import ASSET, INVOICE, PROJECT, STORE
from whollycrypto import InvalidSignatureError, ValidationError, parse_notification, verify_signature

SECRET = "only-an-isolated-signature-fixture"
NOW = 1800000000


def signed(raw):
    return (
        "t="
        + str(NOW)
        + ",v1="
        + hmac.new(SECRET.encode(), str(NOW).encode() + b"." + raw, hashlib.sha256).hexdigest()
    )


class WebhookTests(unittest.TestCase):
    def test_documented_callback_snapshot_all_statuses(self):
        payload = json.loads((Path(__file__).resolve().parents[1] / "examples/notification.json").read_text())
        self.assertEqual(2, payload["payload_version"])
        self.assertEqual("49.9", payload["amount"])
        self.assertEqual("EUR", payload["currency"])
        self.assertEqual("ethereum", payload["paid_chain"])
        self.assertEqual("USDC", payload["paid_asset"])
        self.assertEqual("1.17", payload["settlement_exchange_rate"]["rate"])
        for status in ("new", "processing", "settled", "expired", "invalid", "cancelled"):
            case = {**payload, "status": status}
            if status != "settled":
                for key in ("paid_chain", "paid_asset", "paid_payment_method_id", "settlement_exchange_rate"):
                    case[key] = None
            raw = json.dumps(case).encode()
            headers = {"Wholly-Signature": signed(raw), "Wholly-Event-Id": payload["event_id"], "Wholly-Delivery-Id": STORE}
            parsed = parse_notification(raw, headers, SECRET, now=NOW)
            self.assertEqual(status, parsed.status)
            self.assertEqual(case["paid_chain"], parsed.payload["paid_chain"])
            self.assertEqual(case["settlement_exchange_rate"], parsed.payload["settlement_exchange_rate"])
            with self.assertRaises(InvalidSignatureError):
                parse_notification(raw.replace(b"1.17", b"9.99") + b" ", headers, SECRET, now=NOW)
            with self.assertRaises(InvalidSignatureError):
                parse_notification(raw, {**headers, "Wholly-Event-Id": PROJECT}, SECRET, now=NOW)
            with self.assertRaises(InvalidSignatureError):
                parse_notification(raw, headers, "another-endpoint-secret", now=NOW)

    def setUp(self):
        self.raw = json.dumps(
            {
                "invoice_id": INVOICE,
                "sequence": 3,
                "status": "settled",
                "amount": "25.00",
                "currency": "EUR",
                "metadata": {"values": [1, 2]},
            }
        ).encode()
        self.headers = {
            "Wholly-Signature": signed(self.raw),
            "WHOLLY-EVENT-ID": PROJECT,
            "Wholly-Delivery-Id": STORE,
        }

    def test_exact_byte_hmac_and_clock_window(self):
        for now in (NOW - 300, NOW, NOW + 300):
            self.assertTrue(verify_signature(self.raw, signed(self.raw), SECRET, now=now))
        for now in (NOW - 301, NOW + 301):
            self.assertFalse(verify_signature(self.raw, signed(self.raw), SECRET, now=now))
        self.assertFalse(verify_signature(self.raw + b" ", signed(self.raw), SECRET, now=NOW))
        self.assertFalse(verify_signature(self.raw, signed(self.raw), "wrong", now=NOW))
        self.assertTrue(verify_signature(self.raw, signed(self.raw), SECRET.encode(), now=NOW))

    def test_bad_signature_formats_and_local_configuration(self):
        for signature in (
            None,
            "",
            signed(self.raw) + "\n",
            signed(self.raw).replace("t=", "t=0"),
            signed(self.raw) + ",v1=" + "a" * 64,
            "t=9999999999999,v1=" + "a" * 64,
        ):
            self.assertFalse(verify_signature(self.raw, signature, SECRET, now=NOW))
        self.assertFalse(verify_signature(b"x" * 262145, signed(self.raw), SECRET, now=NOW))
        for call in (
            lambda: verify_signature(self.raw.decode(), signed(self.raw), SECRET),
            lambda: verify_signature(self.raw, signed(self.raw), ""),
            lambda: verify_signature(self.raw, signed(self.raw), SECRET, tolerance_seconds=True),
            lambda: verify_signature(self.raw, signed(self.raw), SECRET, now=-1),
        ):
            with self.assertRaises(ValidationError):
                call()

    def test_parse_readonly_payload_and_unsigned_identifiers(self):
        result = parse_notification(self.raw, self.headers, SECRET, now=NOW)
        self.assertEqual(INVOICE, result.invoice_id)
        self.assertEqual(3, result.sequence)
        self.assertEqual("settled", result.status)
        self.assertEqual(PROJECT, result.event_id)
        self.assertNotIn("25.00", repr(result))
        with self.assertRaises(FrozenInstanceError):
            result.event_id = ASSET
        with self.assertRaises(TypeError):
            result.payload["status"] = "invalid"
        with self.assertRaises(TypeError):
            result.payload["metadata"]["values"][0] = 3
        # Event header is not covered by HMAC. Receivers MUST also deduplicate invoice+sequence.
        changed = parse_notification(self.raw, {**self.headers, "WHOLLY-EVENT-ID": ASSET}, SECRET, now=NOW)
        self.assertEqual(ASSET, changed.event_id)
        self.assertEqual(result.invoice_id, changed.invoice_id)

    def test_duplicate_and_malformed_headers(self):
        for headers in (
            None,
            [],
            [("Wholly-Signature", signed(self.raw)), *self.headers.items()],
            {**self.headers, "wholly-signature": signed(self.raw)},
            {**self.headers, "WHOLLY-EVENT-ID": "invalid"},
            {**self.headers, "Wholly-Delivery-Id": [STORE]},
        ):
            with self.subTest(headers=type(headers).__name__), self.assertRaises(InvalidSignatureError):
                parse_notification(self.raw, headers, SECRET, now=NOW)

    def test_signed_payload_shape_rejection(self):
        for payload in (
            [],
            {},
            {"invoice_id": INVOICE, "status": "settled", "sequence": True},
            {"invoice_id": INVOICE, "status": "settled", "sequence": 0},
            {"invoice_id": INVOICE, "status": "settled", "sequence": 9_223_372_036_854_775_808},
            {"invoice_id": "not-a-uuid", "status": "settled", "sequence": 1},
            {"invoice_id": INVOICE, "status": "invented", "sequence": 1},
        ):
            raw = json.dumps(payload).encode()
            with self.subTest(payload=payload), self.assertRaises(InvalidSignatureError):
                parse_notification(raw, {**self.headers, "Wholly-Signature": signed(raw)}, SECRET, now=NOW)
        raw = b'{"invoice_id":"' + INVOICE.encode() + b'","status":"new","status":"settled","sequence":1}'
        with self.assertRaises(InvalidSignatureError):
            parse_notification(raw, {**self.headers, "Wholly-Signature": signed(raw)}, SECRET, now=NOW)


if __name__ == "__main__":
    unittest.main()
