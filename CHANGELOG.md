# Changelog

## 2.2.0 - 2026-09-15

- Document per-invoice chain/asset selection for merchant 5.1.0+, including separate Bitcoin Lightning selection.
- Refresh public API request fixtures and verify exact JSON lists and idempotent retries. Omitted selections retain existing behavior.

## 2.1.0 - 2026-09-14

- Support merchant 4.1.0 rich IPN/webhook payload version 2, including signed event identity and project/store scope. Retained legacy events remain supported.
- Add paginated invoice payment-history reads, with exact amounts, rail/asset identifiers and invalidated observations.
- Update receiver examples to compare invoice-state fields when deduplicating a revision, so separate events at the same sequence are accepted. Reject wrong signed project scope and conflicting state.
- Document locked rates versus advisory market snapshots, tolerance, confirmation handling, truncation, privacy and safe fulfilment. Refresh every public API fixture and callback example.

## 2.0.0 - 2026-09-14

- Target merchant 4.0.0: invoice responses use `invoice_id`, matching IPN/webhooks; `public_id` is removed by the server. Update custom response readers before upgrading the merchant.
- Refresh all request/response fixtures, create/list examples and history documentation. Python 3.10+ support and callback verification are unchanged.

- Explain IPN versus webhook selection and secrets, all invoice statuses and the complete callback body.
- Add callback setup/worker guidance and a verified JSON sample in examples, with links to the live documentation.
- Show string casts for amount variables and explain why floating-point calculations lose precision.


## 1.0.1 - 2026-09-14

- Document manual ZIP installation without pip, build tools or third-party packages.
- Add examples for a copied local package and an intact SDK folder, including direct `whollycrypto.Client(...)` usage.
- Test manual loading in fresh Python processes without site-packages or package metadata, including invoice precision and webhook verification.
- No API, request encoding, invoice idempotency or callback-signature changes. Still targets merchant API v1, tested against merchant 3.5.0.

## 1.0.0 - 2026-09-13

- Initial Python 3.10+ SDK for all 17 merchant API v1 endpoints, tested against merchant 3.5.0.
- Exact decimal strings/Decimal support, preserved response envelopes and large integers.
- Explicit invoice idempotency, deterministic body encoding and bounded opt-in safe retries.
- HTTPS connection reuse, certificate verification, bounded responses and quota headers.
- Separate token-free public checkout reader, preserving Lightning and chain payment fields.
- IPN/webhook verification, replay-aware durable SQLite inbox example and typed exceptions.
- MIT license, type information and no third-party runtime dependencies.
- 31 isolated tests pass on Python 3.10, 3.12 and 3.14; all public API contract fixtures match.
