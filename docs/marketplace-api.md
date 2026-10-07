# Marketplace API

## Merchant 8.1 safety rules

- Changing or removing a vendor commission needs `commissions.override` as
  well as `vendors.write`. Invoice commission overrides need the same financial
  scope. An unchanged commission does not add a permission requirement.
- Overpayments alone do not block quoted vendor shares on Bitcoin or supported
  EVM coins/ERC-20 tokens. Excess stays separate; payouts never reprice the split.
  Keep separate native funds for fees and Bitcoin change dust if needed.
- A vendor with open or unpaid obligations cannot be archived. To restore an
  already archived vendor, call update with active/suspended status and
  `reconciliation.write`; existing allocations are unchanged.
- Explicit resume can replace only a sufficiently confirmed canonical EVM revert
  proven by two independent providers. Original hashes/fees stay recorded and
  consume the original fee cap. Unknown outcomes or partial token delivery stay
  held (`payout_recovery_unverified`); never create a second payout to bypass it.
- Automatic policies defer credit pauses fairly and hold invalid whole invoice
  groups without blocking other eligible invoices.

Existing clients use the same routes and request shapes; no SDK upgrade is
required for these server-side fixes. Follow the public reference linked below.


Requires merchant **8.0.0+**, Marketplace enabled for the project and a separate
`wc_marketplace_...` key from Settings → API access. Ordinary merchant, Operator
and MCP keys do not grant payouts. Keep this client on a trusted backend;
never embed a spending credential in a browser, mobile app or downloadable file.

[Full API reference](https://www.whollycrypto.com/api/#marketplace) ·
[Setup guide](https://www.whollycrypto.com/documentation/#marketplace) ·
[Multiple-vendor tutorial](https://www.whollycrypto.com/tutorials/marketplace/)

## Safe workflow

1. Create vendors and their payout destinations. Verify each address and network
   with its owner, then separately approve it. Register BTC mainnet or a supported
   EVM destination for every vendor that will share an invoice.
2. Create one Marketplace invoice with exact-string `amount`, `store_id` and
   `allocations`. Gross vendor shares must add up exactly to the invoice total.
   Ordinary invoice checkout, payment evidence and IPN still work normally.
3. Wait for allocations to become available. A settled invoice alone does not
   prove funds are sufficiently confirmed for a payout. Underpayment, ambiguous
   receipts or a reorg can hold the allocation.
4. Prepare a same-asset payout with exact atomic fee/gas caps. Inspect the retained
   recipients, amount, `plan_hash` and `revision` before calling `approvePayout`
   (`approve_payout` in Python). Preparation never broadcasts.
5. Follow `getPayout` / `get_payout` until independent confirmation. Keep separate
   unreserved native coins for network fees; vendor principal is never reduced.
   Automatic policies are opt-in and require bounded principal, fee and gas limits.

All methods take the project UUID first, even when a resource UUID is supplied.
Reads return normal dictionaries/objects with `data` and, for lists,
`pagination.page/per_page/total/pages`. Page sizes range from 1 to 100. Use the
UUIDs returned by the API; asset symbols alone are not immutable asset identities.

Every write requires a persisted 16–128 character idempotency key. Retry a failed
request with the same key and exact instructions. Never create a new payout just
because a request timed out. Clients do not retry by default; explicit retry
options reuse the same request. Do not serialize clients or log API keys.

A $300 invoice with three $100 shares and 4% commission allocates the received
asset proportionally: $96-equivalent per vendor and $12-equivalent gross
commission at the invoice quote. Rounding preserves each atomic unit. Later fiat
values can change. Wholly's configured processing fee applies once to the original
invoice, separately from commission and network fees, not once per vendor.

## Events and recovery

Marketplace webhooks use a **separate signing secret** and the normal
`Wholly-Signature: t=...,v1=...` HMAC protocol. Verify the exact raw body, timestamp,
authenticated `project_id`, `payload_version: 1`, `event_id` and `event_type`.
Use the signed receiver example alongside this SDK, not the invoice notification
parser. Store event IDs uniquely and acknowledge only after durable acceptance.

`marketplace.payout.broadcast` is not final. Use
`marketplace.payout.confirmed` for independently confirmed vendor payouts.
`marketplace.refund.confirmed` concerns a customer refund. Delivery is at least
once; retries do not authorize another transfer. Refresh a payout's retained
state to reconcile delayed/out-of-order events.

Full same-asset refunds require a verified customer address and separate approval.
Before payout they reserve unpaid funds. After all vendors were paid they need
separate free primary-wallet funds; vendors are not debited or clawed back.
Mixed-method or partially completed vendor batches require review, not an unsafe
forced refund. Emergency pause stops new spending while preserving history.
