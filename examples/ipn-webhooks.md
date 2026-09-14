# Receive IPN and webhooks

Use [webhook_wsgi.py](webhook_wsgi.py) for either channel. Both send the same JSON; configure each receiver with the correct secret.

## Set up the two channels

| Channel | Where you configure it | What arrives | Secret |
| --- | --- | --- | --- |
| IPN | Store → IPN, plus the store default URL or `ipn_url` on invoice creation | Every generated invoice event | Store IPN signing secret |
| Webhook | Store → Webhooks → endpoint URL and selected events | Only your selected events | That endpoint's own signing secret |

Use separate trusted routes or application instances (for example `/callbacks/wholly-ipn` and `/callbacks/wholly-webhook`) with their respective secrets. Do not choose a secret from unverified request data. Neither secret is your merchant API token. Rotating the IPN secret does not rotate webhook secrets. Enabling both can deliver the same invoice revision twice.

Mount `create_app(signing_secret, private_sqlite_path, configured_project_id)` behind your HTTPS WSGI server. Python 3.10+; only the SDK and standard library are needed. The module does not start a server. Create a private 0700 queue directory outside the web root, owned by the application user. See the main README for pip-free imports.

## What the POST contains

[notification.json](notification.json) is a complete synthetic callback body, for a €49.90 invoice settled under the store's rules:

```json
{
  "invoice_id": "11111111-2222-4333-8444-555555555555",
  "status": "settled",
  "amount_status": "paid",
  "timing_status": "on_time",
  "resolution": "automatic",
  "sequence": 3,
  "amount": "49.9",
  "currency": "EUR",
  "order_id": "order-1042"
}
```

The nine fields above are the entire body, not an envelope. `invoice_id` is the **public** invoice UUID. `amount` is the original invoice total, **not the crypto received**. It remains EUR even when the customer pays USDC. Keep decimal amounts as strings.

| Invoice `status` | Meaning |
| --- | --- |
| `new` | Awaiting payment |
| `processing` | Payment detected; amount or finality still missing |
| `settled` | Accepted under invoice rules, or manually |
| `expired` | Deadline passed; late monitoring can continue |
| `invalid` | Payment cannot be accepted automatically, evidence lost, or rejected |
| `cancelled` | Cancelled; this does not refund a payment |

`amount_status`: `none`, `partial` (underpaid), `paid` (including allowed tolerance), or `overpaid`. `timing_status`: `on_time` or `late`. `resolution`: `automatic`, `manually_settled` or `manually_invalidated`.

Subscription events are `invoice.created`, `payment.received`, `invoice.processing`, `invoice.settled`, `invoice.expired`, `invoice.invalid` and `invoice.cancelled`. **Event names are not transmitted in the body or headers.** Inspect the status fields. A payment event and status event can share the same body/sequence. There is no `invoice.paid` event. Not all states occur; zero-confirmation payments may settle immediately and permitted zero-amount invoices settle without payment.

Callbacks do not include transaction hashes, chain/token, crypto amounts, confirmations, customer details, metadata, project/store IDs or checkout URLs. Fetch the authenticated invoice for those fields:

```python
# After parse_notification() has verified the raw bytes:
status = notice.status
amount_state = notice.payload["amount_status"]
invoice_total = notice.payload["amount"]  # "49.9", not USDC received
# In your durable worker, using the project's configured API host and token:
detail = client.get_invoice(configured_project_id, notice.invoice_id)
invoice = detail["data"]
# Match your stored order, project/store, amount and currency before fulfilment.
# Only invoice["status"] == "settled" is eligible; commit order updates once.
```

This snippet is for your worker, not the HTTP acknowledgement path. It does not implement order matching or fulfilment; those depend on your shop's database and business rules. The receiving examples only verify and queue.

## Verify, queue, acknowledge

1. Verify `Wholly-Signature` against the **exact raw body** before JSON parsing. HMAC-SHA256 signs `timestamp + "." + raw_body`; header format: `t=<unix-seconds>,v1=<hex>`. The SDK rejects invalid signatures and timestamps outside five minutes by default. Keep clocks synchronized.
2. Commit to a durable inbox before returning HTTP 2xx. Failed storage must return a failure so delivery can retry. The sender times out after 10 seconds and does not follow redirects.
3. Deduplicate the signed `invoice_id` and `sequence`, scoped to the **configured project**. Keep `Wholly-Event-Id` and `Wholly-Delivery-Id` for diagnostics; these headers are **not signed** and must not be your sole replay key. A conflicting signed body for the same revision needs review.
4. Fetch the authenticated invoice, validate its order/project/store/amount/currency against your records, and fulfil only on `settled`. Process each order transactionally once. Never let an older sequence overwrite a newer one; status can change through reconciliation, so do not assign statuses a permanent rank.

IPN retries retryable failures up to eight attempts: immediately, then delays of 10 seconds, 1 minute, 5 minutes, 15 minutes, 1 hour, 6 hours and 24 hours **after the previous attempt finishes**. Webhook automatic retries can be disabled. Delayed, duplicate and out-of-order messages are normal. Retry signatures use a new timestamp; manual redelivery keeps the event ID but creates a new delivery ID. Payload retention is 90 days. Low processing credits pause deliveries, not incoming payments.

In merchant 4.0.0+, creation/detail returns `data.invoice_id` and invoice list rows use `invoice_id`, matching this callback ID. The old `public_id` field is removed. Use the same value to fetch the invoice; never use internal `id` or `order_id` in the invoice URL.

Open **Invoice → Details → IPN History / Webhook History** for that invoice's collapsed delivery lists. **Store → IPN / Webhooks → History** searches across invoices by order, invoice ID, email or name. **Details** opens a modal with the saved body/status, target and delivery result. Current customer metadata is shown separately; it is not part of the callback. Expired payloads are never recreated.

[Integration guide](https://www.whollycrypto.com/documentation/#delivery-history) · [Full callback contract and payload](https://www.whollycrypto.com/api/#notifications) · [Invoice detail API](https://www.whollycrypto.com/api/#get-invoice)

Your installation also has **Settings → API access → API documentation → Dynamic IPN & webhooks** (`/settings/api/docs/#notifications`). The public docs describe the latest merchant version; check your installed reference when running an older version.
