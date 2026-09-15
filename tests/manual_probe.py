"""Run beside a manually copied SDK in a fresh interpreter with site disabled."""

import hashlib
import hmac
import json
import sys
from pathlib import Path

if sys.argv[1] == "source":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "whollycrypto-python-sdk" / "src"))

import whollycrypto
from whollycrypto import Client

assert Client is whollycrypto.Client
assert whollycrypto.__version__ == "2.3.0"
assert Path(whollycrypto.__file__).resolve().is_relative_to(Path(__file__).resolve().parent)
assert not any("site-packages" in path or "dist-packages" in path for path in sys.path)
project = "11111111-1111-4111-8111-111111111111"
store = "22222222-2222-4222-8222-222222222222"
invoice = "33333333-3333-4333-8333-333333333333"
amount = "0.123456789012345678901234567890"
token = "wc_fixture_not_a_real_credential"


class FixtureTransport:
    def send(self, request, options):
        assert request.headers["Authorization"] == "Bearer " + token
        assert request.headers["Idempotency-Key"] == "saved-manual-fixture-key"
        assert request.body == json.dumps({"amount": amount, "currency": "EUR"}, separators=(",", ":")).encode()
        return whollycrypto.Response(
            200,
            {"Content-Type": "application/json"},
            json.dumps({"data": {"invoice_id": invoice, "amount": amount}}).encode(),
        )


with whollycrypto.Client("https://api.example.test", token, transport=FixtureTransport()) as client:
    result = client.create_invoice(
        project, store, {"currency": "EUR", "amount": amount}, "saved-manual-fixture-key"
    )
    assert result["data"]["invoice_id"] == invoice
    assert result["data"]["amount"] == amount

raw = json.dumps({"invoice_id": invoice, "sequence": 1, "status": "settled"}).encode()
now = 1800000000
secret = "isolated-manual-sdk-signature-fixture"
signature = "t=" + str(now) + ",v1=" + hmac.new(
    secret.encode(), str(now).encode() + b"." + raw, hashlib.sha256
).hexdigest()
headers = {"Wholly-Signature": signature, "Wholly-Event-Id": project, "Wholly-Delivery-Id": store}
assert whollycrypto.parse_notification(raw, headers, secret, now=now).invoice_id == invoice
assert not whollycrypto.verify_signature(raw, signature, "incorrect", now=now)
print("PASS: manual imports, exact invoice bytes and webhook signatures; no pip or live requests.")
