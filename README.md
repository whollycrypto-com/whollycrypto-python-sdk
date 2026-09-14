# Wholly Crypto Python SDK

**Merchant 4 upgrade:** read `data.invoice_id` from invoice creation/detail and `invoice_id` from list rows. It matches the callback `invoice_id`. The server no longer returns `public_id`; internal `id` is not a checkout ID. Update custom response readers before upgrading your merchant. For older merchants, keep SDK 1.x or explicitly handle their older response shape.

The official Python client for your **self-hosted Wholly Crypto merchant API**.
Create invoices, check payments, manage accepted assets and verify IPN/webhooks.

Python **3.10+**. Standard library only, with **no runtime dependencies**.
SDK **2.0.0** targets API **v1**, tested against merchant **4.0.0**.
SDK and merchant versions are independent.

## Install

### With pip

```bash
python -m pip install whollycrypto
```

Use a virtual environment for your application. Import the package as `whollycrypto`.

### Without pip (manual download)

1. [Download SDK 2.0.0 as a ZIP](https://github.com/whollycrypto-com/whollycrypto-python-sdk/archive/refs/tags/v2.0.0.zip).
2. Extract it and copy the complete **`src/whollycrypto/` folder** beside your
   application script. Keep the SDK's `LICENSE` with your copy. Do not copy only `__init__.py`.
3. Import it normally. No pip, build tools or third-party packages are needed:

```python
import os
import whollycrypto

with whollycrypto.Client(
    "https://api.your-domain.com",
    os.environ["WHOLLY_API_TOKEN"],
) as client:
    # Use the invoice/payment methods below here.
    pass
```

Your layout should be `your-app/app.py` and `your-app/whollycrypto/__init__.py`
(plus the other files inside `whollycrypto/`). Do not name your script `whollycrypto.py`;
it would hide the SDK package. Python 3.10+ with SSL support is still required.
Set `WHOLLY_API_TOKEN` on your server using a credential from **Settings → API access**.
`import whollycrypto` / `whollycrypto.Client(...)` and `from whollycrypto import Client`
both work, with the same API and signature helpers as a pip installation.

**Keep the downloaded SDK folder intact instead?** Rename it to
`whollycrypto-python-sdk`, place it beside your script and load its `src/` directory:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "whollycrypto-python-sdk" / "src"))
import whollycrypto
```

Use only a trusted, fixed local path, never one from a customer's request. This
also lets you run a downloaded example with a local `PYTHONPATH` pointing to that
`src/` directory. For manual updates, replace the SDK folder with a newer tagged
download; keep your application code and credentials outside it.

## Create an invoice

Use **your installation's API domain**, not its merchant-console or checkout domain.
Create a credential in **Settings → API access** with read/write access to the project.

Find both UUIDs under **Project → Stores → select store → Basic → API IDs**.
Copy **Project API ID** and **Store API ID**, not the readable project/store identifiers.
Projects and stores are created in the console; the public API does not list or create them.

```python
import os
from whollycrypto import Client

# Persist this key AND the exact payload with your order before the request.
# Reuse the same key, credential and payload if the response is lost.
idempotency_key = "order-1042-payment-attempt-1"

with Client("https://api.your-domain.com", os.environ["WHOLLY_API_TOKEN"]) as client:
    result = client.create_invoice(
        "11111111-1111-4111-8111-111111111111",  # Your Project API ID
        "22222222-2222-4222-8222-222222222222",  # Your Store API ID
        {
            "amount": "49.90",  # From a variable: "amount": str(amount)
            "currency": "EUR",
            "order_id": "order-1042",
            "email": "customer@example.com",
            "description": "Annual plan",
            "ipn_url": "https://your-shop.com/wholly/ipn",
            "redirect_url": "https://your-shop.com/orders/1042",
            "cancel_url": "https://your-shop.com/cart",
        },
        idempotency_key=idempotency_key,
    )

public_invoice_id = result["data"]["invoice_id"]
checkout_url = result["links"]["checkout"]
```

The UUIDs above are placeholders. Return `checkout_url` to your customer, or redirect
from your server. Never put an API token in browser JavaScript, HTML, checkout URLs
or source control. A return/success URL is **not proof of payment**.

Every API method returns the **complete response envelope**. Fields such as `data`,
`links`, `pagination` and reconciliation's separate top-level fields are preserved.
The SDK does not rename fields or round amounts. JSON fractional numbers decode as
`decimal.Decimal`; monetary strings and arbitrarily large JSON integers stay exact.

## Check and list payments

Reuse one client per worker/request context, then close it. The default transport
reuses its HTTPS connection. Calls are synchronous; run them outside an async event
loop or in a thread worker. Do not share a client across concurrent workers, because
`last_response` describes its most recent call.

```python
invoice = client.get_invoice(project_id, public_invoice_id)["data"]
if invoice["status"] == "settled":
    # Match the stored order, amount/currency and project/store first.
    # Fulfil exactly once using your database's transaction/idempotency mechanism.
    pass

page = client.list_invoices(project_id, {
    "store_id": store_id, "status": "settled", "search": "order-1042",
    "limit": 50, "offset": 0,
})

for invoice in client.iter_invoices(project_id, {"status": "settled"}):
    # Each next page is requested only when needed.
    pass
```

These snippets use an open `client`. Invoice paths use `invoice_id`, **not** internal
`id` or `order_id`. `processing` is not `settled`. Pages are separate snapshots, so
deduplicate by public invoice ID if exporting while new invoices are arriving.

## Amounts and invoice options

Amount, spread, tolerance and fixed token prices accept plain decimal strings or
`Decimal`. Floats are rejected for these fields. `Decimal` values are encoded as
plain strings without exponent notation. Other request values use normal JSON types.

```python
from decimal import Decimal

payload = {
    "amount": Decimal("25.00"),
    "currency": "USD",
    "exchange_rate_spread_percent": "0.5",
    "underpayment_tolerance_percent": "1",
    "expires_in_seconds": 900,
    "language": "de",
    "metadata": {
        "firstname": "Ada", "lastname": "Lovelace",
        "street": "12 Example Street", "street2": "Suite 2", "zip": "10115",
        "city": "Berlin", "country": "Germany", "countryiso2": "DE",
        "company": "Example GmbH", "vatid": "DE123456789",
    },
    "checkout_appearance": {
        "title": "Complete your order", "intro": "Thanks for choosing us.",
        "outro": "Questions? https://your-shop.com/help",
        "intro_font_size": 18, "outro_font_size": 16,
        "theme": "light", "accent_color": "#1768CE",
    },
}
```

Omitted options inherit store settings. Use `{}` for objects, not `[]`.
An empty `checkout_appearance` object freezes the resolved store design for that
invoice; omitting it keeps normal store appearance behavior. Appearance accepts
structured settings, not arbitrary HTML, JavaScript or CSS. The server remains
authoritative for currencies, allowed assets, confirmation policy and validation.

Request object keys are sorted for deterministic bytes. List order, strings and
decimal precision are preserved. Never switch SDKs/encodings during an invoice retry:
the server binds idempotency to the original credential and **exact raw JSON bytes**.
`Client.new_idempotency_key()` generates a key; you must persist it before use.

## Merchant API methods

| Method | Purpose |
| --- | --- |
| `service_info()` / `health()` | Public service/health; no token sent |
| `create_invoice(project, store, payload, idempotency_key)` | Create or safely replay an invoice |
| `get_invoice(project, invoice_id)` | Private invoice detail and current checkout link |
| `list_invoices(project, filters)` / `iter_invoices(project, filters)` | Search and paginate invoices |
| `list_project_payment_assets(project)` | Native/token policies and readiness |
| `update_project_payment_asset(project, asset, policy)` | Update a project asset policy |
| `list_token_candidates(project, chain_slug, filters)` | Search catalog tokens with `q` and `limit` |
| `register_token_asset(project, token)` | Verify/register a catalog token |
| `discover_custom_dex_pools(project, chain_slug, contract)` | Discover supported DEX pricing candidates |
| `register_custom_token(project, token)` | Verify/register a custom contract or mint |
| `list_store_payment_assets(project, store)` | Accepted on-chain assets and separate Lightning readiness |
| `update_store_payment_assets(project, store, assets)` | **Replace** the entire on-chain selection |
| `update_store_confirmation_policy(project, store, asset, policy)` | Inherit or override confirmations |
| `list_project_wallets(project)` | Public addresses and balances; no keys |
| `list_reconciliation(project, filters)` | Needs-attention queue, fixed 25 cases per page |
| `get_reconciliation(project, invoice_id, page=1)` | Detail and paginated decision history |

IDs accept strings or `uuid.UUID`. See the
[full API reference](https://www.whollycrypto.com/api/) and
[payment-method examples](https://github.com/whollycrypto-com/whollycrypto-python-sdk/blob/main/docs/payment-methods.md).

`update_store_payment_assets()` receives the list itself, not an `assets` wrapper.
`[]` removes **all on-chain selections**. It does not configure Lightning.
Refunds, sends, reconciliation decisions, accounts, exchange credentials and Lightning
configuration are console-only; the SDK does not invent public routes for them.

Keep amounts as decimal strings from the start. `str(amount)` converts a variable to the required string type, but cannot recover precision already lost through floating-point calculations. Keep the original decimal text or use `Decimal`; do not calculate payment totals with floats.

## Verify IPN and webhooks

IPN sends every generated invoice event to the store default URL or invoice's
`ipn_url`. Webhooks send only selected events. Both deliver the same JSON snapshot.
Use **Store → IPN's secret for IPN** and **the individual webhook endpoint's secret
for webhooks**, never an API token. Rotating one does not rotate the others.
Pass the exact raw body as `bytes`.

**Fulfil on `status = settled`, not `processing` or `amount_status = paid`.**
Invoice statuses are `new`, `processing`, `settled`, `expired`, `invalid`, `cancelled`.
Underpaid/overpaid use `amount_status`; lateness uses `timing_status`.
The body contains `invoice_id` (public UUID), `status`, `amount_status`,
`timing_status`, `resolution`, `sequence`, `amount`, `currency`, `order_id`.
`amount` is the invoice total, not crypto received. Event names, transaction hashes,
chain/token, customer data and metadata are not sent; fetch the full invoice via API.

[IPN/webhook setup and receiver example](examples/ipn-webhooks.md) ·
[Integration guide](https://www.whollycrypto.com/documentation/#delivery-history) ·
[Event table and full payload](https://www.whollycrypto.com/api/#notifications).
Also available in your console at `/settings/api/docs/#notifications`.

```python
from whollycrypto import InvalidSignatureError, parse_notification

try:
    notice = parse_notification(raw_body, request_headers, signing_secret)
except InvalidSignatureError:
    # Return HTTP 400 without logging secrets or the customer's payload.
    raise

# Durably enqueue before returning 2xx. Failed storage must not be acknowledged.
# Persist (configured_project_id, notice.invoice_id, notice.sequence) for deduplication.
# Your worker re-fetches the invoice through the authenticated client before fulfilment.
```

Verification uses HMAC-SHA256 and a constant-time comparison, with a five-minute
past/future clock window. Keep your server clock synchronized. `verify_signature()`
is also available for signature-only checks. `parse_notification()` additionally
validates UUIDs, status and sequence, then returns a readonly `Notification` payload.
`notice.invoice_id` is the **public** invoice UUID.

Signatures cover the timestamp and raw body, **not** event/delivery ID headers.
Do not deduplicate using event ID alone: changing it must not let an attacker
bypass replay protection, and a forged collision must not suppress a different
signed invoice. Use the signed invoice ID and sequence, scoped to your configured
project. Keep invoice state monotonic and re-check the authenticated invoice.
Event names are not sent in the payload or headers.

The [WSGI inbox example](https://github.com/whollycrypto-com/whollycrypto-python-sdk/blob/main/examples/webhook_wsgi.py)
verifies before storage, queues durably in private SQLite, handles duplicates and
does not acknowledge failed writes. It does **not** fulfil orders or start a web
server. Mount it behind your application's HTTPS server and implement an idempotent
worker. The example's private filesystem checks target Linux/POSIX deployments.

## Errors, timeouts and retries

```python
from whollycrypto import APIError, Client, Options, TransportError

client = Client("https://api.your-domain.com", token, options=Options(
    timeout_seconds=20, connect_timeout_seconds=5,
    max_retries=1, max_retry_delay_seconds=30,
))
try:
    result = client.get_invoice(project_id, public_invoice_id)
except APIError as error:
    status = error.status_code
    code = error.error_code
    retry_after = error.retry_after  # Seconds or None
    # error.api_message / error.response.body are opt-in private details, not log text.
except TransportError:
    # A timeout does NOT prove invoice creation failed.
    # Retry its original payload with the same stored key and credential.
    pass
finally:
    client.close()
```

Retries are **off by default**. With retries enabled, only GETs and invoice creation
with its explicit key can retry transient connections or HTTP 429/502/503/504.
Other writes never retry automatically. Retries reuse the immutable request and
honor `Retry-After` seconds or a standard HTTP date. Invalid headers or waits longer
than the configured limit are surfaced to your queue, never retried early.
At most three retries can be enabled. Include attempts/backoff in your worker budget;
network timeouts depend on the operating system's DNS/socket behavior.

`client.last_response.rate_limit()` returns `limit`, `remaining` and `reset` headers
when present. `last_response` is `None` if the most recent attempted request has no
HTTP response. The default limit is 8 MiB per response and 32 KiB per merchant request.

TLS verification is always enabled. No automatic redirects, cookie storage, proxy
environment discovery or `.netrc` lookup. `Options(ca_file="/path/to/ca.pem")` can
trust your private CA without disabling hostname verification. A custom transport
receives credentials and must be trusted. Closing a client closes its default
transport; injected/shared transports remain caller-owned.

Repr and normal SDK exception messages omit credentials and response bodies.
Python debuggers can still inspect private attributes and frame locals: disable
local-variable/body capture in production error monitoring and never pickle clients.

## Public checkout and Lightning

```python
from whollycrypto import CheckoutClient

with CheckoutClient("https://pay.your-domain.com") as checkout:
    view = checkout.get_invoice(public_invoice_id)
    url = checkout.invoice_url(public_invoice_id)
```

This separate reader never holds or sends a merchant API token. It also exposes
`get_preview(project, store=None)` and `preview_url(project, store=None, state="waiting")`.
Preview states are illustrative, not evidence of payment. Use the QR and image URLs
returned by checkout JSON instead of reconstructing them.

Preserve `payment_rail`, `asset_decimals`, destination tags/memos, `payment_uri` and
`payable`. Lightning BTC uses **11 atomic decimals (millisatoshis)**; on-chain BTC
uses 8. Its payment hash is not an on-chain address. Use the BOLT11/payment URI.
The SDK never signs or sends funds.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -t . -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Tests cover all 17 merchant endpoints, validation, precision, retry identity, HTTP
connection reuse, TLS rejection, signature verification and the durable receiver.
They use only mocks/disposable loopback servers and SQLite, never live payments.
Tests require OpenSSL CLI, SSL and SQLite support. Plain HTTP is available only for
explicit `Options(allow_insecure_localhost=True)` tests on localhost/127.0.0.1/::1;
this never disables HTTPS certificate verification.

An optional Python 3.10–3.14 CI template is provided in
[ci/github-actions.yml](https://github.com/whollycrypto-com/whollycrypto-python-sdk/blob/main/ci/github-actions.yml).
Enabling it requires a maintainer with workflow-write permission. See
[maintenance notes](https://github.com/whollycrypto-com/whollycrypto-python-sdk/blob/main/docs/maintaining.md)
for API drift checks and release verification.

## License

[MIT](https://github.com/whollycrypto-com/whollycrypto-python-sdk/blob/main/LICENSE),
for this client SDK only. The merchant application and other Wholly Crypto software
have their own licenses. No server implementation or private-service code is included.
