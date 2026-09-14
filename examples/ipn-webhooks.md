# IPN & webhooks

Use [webhook_wsgi.py](webhook_wsgi.py) as a receiver and [notification.json](notification.json) as a synthetic version-2 example. These examples send no payments and contain no real credentials.

[Setup guide](https://www.whollycrypto.com/documentation/#delivery-history) · [Full field reference](https://www.whollycrypto.com/api/#notifications) · Your console: `/settings/api/docs/#notifications`.

## Choose the receiver

IPN sends every generated invoice event to the invoice's `ipn_url`, or the store default when inherited. It uses the **Store → IPN signing secret**. Webhooks send selected events and each endpoint has **its own signing secret**. Neither uses your API token. Choose the secret from trusted configuration, never unverified request data.

| Event | Invoice status | Meaning |
| --- | --- | --- |
| invoice.created | new | Invoice created and awaiting payment. Also used when a controlled reopen returns an invoice to new. |
| payment.received | Resulting invoice status | A payment was recorded or the received amount increased. Usually processing or settled; this event alone is not proof of settlement. |
| invoice.processing | processing | Payment detected, but the accepted amount or required finality is not yet met. Partial payments are included. |
| invoice.settled | settled | Settlement policy met, or accepted manually. Check resolution and your order before fulfilment. |
| invoice.expired | expired | Payment deadline passed. A late payment can still change the status while monitoring continues. |
| invoice.invalid | invalid | Cannot be accepted automatically, payment evidence was lost, or a merchant rejected it. Review the invoice. |
| invoice.cancelled | cancelled | Invoice cancelled. Do not fulfil; a cancellation does not refund an on-chain payment. |

An amount can be paid while the invoice is still processing. Fulfil only after verified `settled` status and your order checks. Reorgs and late, partial or excess payments may need review. Confirmation changes do not guarantee an event on every block.

## Version 2 payload

Merchant 4.1.0 adds signed event identity, actual chain/token transfers, exact amounts, quote provenance, metadata and customer fields. The original nine invoice fields remain. Already queued legacy events have no `payload_version` and keep their original body.

| Field | Type | Meaning |
| --- | --- | --- |
| invoice_id | UUID | Public invoice UUID, used by the authenticated invoice detail route |
| status | string | Snapshot invoice state: new, processing, settled, expired, invalid, cancelled |
| amount_status | string | none, partial, paid, or overpaid; paid includes the accepted underpayment tolerance, not confirmation finality |
| timing_status | string | on_time or late |
| resolution | string | automatic, manually_settled, or manually_invalidated |
| sequence | integer | Increasing invoice revision; different events can share one revision. Compare without losing integer precision |
| amount | decimal string | Original invoice total, not the received crypto amount; preserve decimal precision |
| currency | string | Currency of amount, e.g. EUR for a EUR invoice paid with USDC |
| order_id | string \| null | Merchant order reference |
| payload_version | integer | 2 for newly generated 4.1.0+ events; absent on retained legacy events |
| event_id | UUID | Signed event identity, unchanged on retries and manual redelivery |
| event_type | string | One of the seven subscription events |
| occurred_at | timestamp | When this immutable event was created, not delivery time |
| project_id | UUID | Merchant project scope; match to configured receiver |
| store_id | UUID | Merchant store scope; match to configured receiver |
| description | string \| null | Original invoice description |
| email | string \| null | Optional customer email at event creation |
| customer | object | Recognized optional customer metadata fields; no guessed or enriched personal data |
| metadata | object | Original merchant metadata as it existed at event creation |
| created_at | timestamp | Invoice creation time |
| updated_at | timestamp | Invoice state update time |
| expires_at | timestamp | Invoice payment deadline |
| monitoring_expires_at | timestamp | Late-payment monitoring deadline |
| settled_at | timestamp \| null | Settlement time |
| paid_chain | string \| null | 4.1.2+: chain slug of the proven settling method, e.g. ethereum; null without a saved qualifying settlement |
| paid_asset | string \| null | 4.1.2+: native coin or token ticker, e.g. BTC, ETH or USDC; a display label, not unique asset identity |
| paid_payment_method_id | UUID \| null | 4.1.2+: settling intent ID; matches payment_info.methods[].payment_method_id and its exact network/contract |
| settlement_exchange_rate | object \| null | 4.1.2+: saved before-spread market snapshot at settlement, with explicit units, currency, source timestamps and quality flags; never repriced on delivery |
| cancelled_at | timestamp \| null | Cancellation time |
| exchange_rate_spread_percent | decimal string | Locked spread, not the current store default |
| underpayment_tolerance_percent | decimal string | Locked invoice tolerance; each method also reports its effective tolerance |
| reason_code | string \| null | Machine-readable state-transition reason |
| requires_review | boolean | Payment exception hint; not permission to fulfil or refund automatically |
| links | object | checkout, authenticated invoice and payments URLs at event creation; null if no active host record |
| payment_info | object | Actual observed methods, exact amounts, locked quote, advisory market snapshot and bounded payment observations; see field groups below |

### Amounts and payment history

`payment_info.methods` contains only observed methods, not every checkout choice. Before a payment, it is empty and `active_payment_method_id` is null. Identify an asset by network plus asset/contract ID, never by ticker alone. Never add BTC, USDC or different network balances together.

Each method includes `amounts`: expected, received, confirmed, unconfirmed, minimum accepted, remaining, remaining-to-full and overpaid amounts. Every amount has an exact `*_atomic` integer-string companion. Preserve strings; use integer/decimal arithmetic, not floats. Lightning BTC uses 11 decimals (millisatoshis); on-chain BTC uses 8.

`remaining_amount` is the accepted minimum minus **received** funds, floored at zero. It is not an instruction to resend unconfirmed funds. `remaining_to_full_amount` ignores tolerance. `unconfirmed_amount` is received minus confirmed. The locked acceptance policy, not a guessed confirmation count, determines settlement. Lightning's effective tolerance is zero.

Histories are bounded: at most eight observed methods and five recent transfers each, or fewer to fit the 64 KiB event limit. Check `method_count`, `methods_truncated`, `payment_count` and `payments_truncated`. For complete **current** history use:

```python
client.list_invoice_payments(project_id, invoice_id, {"limit": 25, "offset": 0})
```

The read-only endpoint is `GET /v1/projects/{project_id}/invoices/{invoice_id}/payments`. Filter by `payment_method_id`; paginate with `limit` and `offset`. Deduplicate live pages by `payment_id`. One transaction can contain several token logs or UTXO outputs. Reorged, replaced and invalid records remain visible with `counts_towards_received: false`. Lightning uses `payment_hash`, not a transaction/explorer URL.

### Locked quote versus market rate

`quote.effective_rate` means **asset units per one invoice currency unit**, including the saved spread. `reference_rate` is before spread. `rounding_adjustment` is the upward difference in crypto units. Provider names and source timestamps describe the original quote. Old invoices have `provenance_available: false` and null historical details.

`market_rate_at_event` is an advisory cache snapshot with source times and stale/fixed/proxy flags. It excludes spread and never changes the amount owed. Unavailable data stays null. No external rate lookup delays a callback. Store-setting changes and retries never rewrite an event's quote, metadata or policy.

### Quick settlement summary (merchant 4.1.2+)

After a proven settlement, top-level `paid_chain` (for example `ethereum`), `paid_asset` (`USDC`) and `paid_payment_method_id` identify the method that settled the invoice. Native coins use the same fields. Use the method ID to find its exact network, contract and amounts in `payment_info.methods`; tickers are not unique and different methods are never added together.

`settlement_exchange_rate` is saved when the invoice settles. It has the same fields as `market_rate_at_event`: decimal-string `rate`, explicit `units`, `currency`, `symbol`, source names/timestamps and stale/fixed/proxy flags. For EUR/USDC, `rate: "1.17"` with `units: "asset_per_invoice_currency"` means **1 EUR = 1.17 USDC**. This is an advisory market observation before spread, not the locked invoice quote or an executed trade. It never changes what the customer owes.

All four summary fields are null before settlement, after invalidation, for older settlements without a saved snapshot, or for manual acceptance without qualifying policy-final funds. Missing prices alone leave the proven `paid_*` identifiers available and the rate null. A stale rate is explicitly flagged. Later payments, retries and redelivery never refresh the settlement snapshot, including a saved null. A genuine re-settlement captures a new snapshot: `observed_at` identifies that capture, while `settled_at` can retain the first settlement time. Old event bodies remain unchanged. Always check the signed invoice status and sequence; the summary is not permission to fulfil independently.

## Important receiver rules

1. Verify the exact raw body bytes, timestamp and HMAC before parsing or storing. Use a 300-second clock tolerance and reject invalid signatures. Proxy/body-parser rewrites break verification.
2. Event/delivery headers are **not signed**. Version 2 has a signed `event_id`, `event_type`, `project_id` and `store_id` in the body; the SDK rejects an event-header/body mismatch. Match project/store to your configured receiver. For legacy events, use configured scope plus signed invoice ID/sequence, not a header-only identity.
3. Commit to a private durable inbox before returning 2xx. On storage failure return an error so Wholly Crypto retries. Do not fulfil an order in the HTTP handler.
4. The supplied order-state inbox deduplicates by configured project + `invoice_id` + `sequence`. Different event types may share that revision. Compare the original nine invoice-state fields, **not the whole JSON body**; event IDs, rates and formatting can differ. Retain the original raw body privately. A changed status/amount at the same revision requires review. If you need every event, deduplicate on the signed v2 event ID instead and still guard fulfilment separately.
5. Re-fetch the invoice from your **configured API origin**, match project, store, order, amount and currency, then fulfil once in a database transaction. Never send a bearer token to an arbitrary URL in a callback. Ignore stale revisions; a checkout redirect is not proof of payment. Reconcile reversals explicitly, not by fulfilling again.
6. Metadata and customer fields are private merchant data. Do not put secrets in metadata or log whole bodies publicly. Callbacks never add wallet keys, recovery words, provider credentials or Lightning preimages. Explorer links are public; protect your own retained customer data.

Delivery is at-least-once, can be delayed/out of order, and keeps the original snapshot on retries and manual redelivery. Signatures use a fresh delivery timestamp. Saved payloads expire after 90 days; an expired body cannot be reconstructed or resent. Low processing credits pause notifications, not customer payments. Review failed deliveries in the console's store or invoice history.

## Upgrade note

Update receivers that require exactly nine fields or compare whole bodies for duplicate invoice revisions. SDK 2.1.0 accepts retained legacy events and the new version-2 payload. The optional fields do not change your invoice total or fulfilment rules.
