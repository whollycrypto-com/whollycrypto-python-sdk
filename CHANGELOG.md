# Changelog

## 1.0.0 - 2026-09-13

- Initial Python 3.10+ SDK for all 17 merchant API v1 endpoints, tested against merchant 3.5.0.
- Exact decimal strings/Decimal support, preserved response envelopes and large integers.
- Explicit invoice idempotency, deterministic body encoding and bounded opt-in safe retries.
- HTTPS connection reuse, certificate verification, bounded responses and quota headers.
- Separate token-free public checkout reader, preserving Lightning and chain payment fields.
- IPN/webhook verification, replay-aware durable SQLite inbox example and typed exceptions.
- MIT license, type information and no third-party runtime dependencies.
- 31 isolated tests pass on Python 3.10, 3.12 and 3.14; all public API contract fixtures match.
