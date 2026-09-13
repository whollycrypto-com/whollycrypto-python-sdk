# Security

Report vulnerabilities privately via the
[Wholly Crypto contact form](https://www.whollycrypto.com/contact/) or
[GitHub private vulnerability reporting](https://github.com/whollycrypto-com/whollycrypto-python-sdk/security/advisories/new).
Never post API tokens, signing secrets, wallet material or customer details in issues.

Use the current 1.x SDK and a security-maintained Python runtime. The SDK talks only
to the merchant API you configure. It does not hold wallet keys, send funds or
implement any private-service or merchant-server logic.

Configure the API origin on your server, never from customer input. Use the smallest
project/access scope needed and source-IP restrictions when appropriate. Keep TLS
verification enabled; only trust reviewed custom transports and CA bundles.

Client/request reprs and ordinary SDK exception messages omit tokens and bodies.
They cannot prevent Python introspection or debugger access. Disable frame-local,
request-body and response-body capture in production monitoring. `APIError.api_message`
and `response.body` explicitly expose private diagnostic data; redact before logging.

Persist an invoice's idempotency key and payload before sending. A timeout is not
proof of failure. Keep the credential, body bytes and key unchanged across retries.
Never silently regenerate a new key after an uncertain outcome.

Verify callback bytes before parsing. HMAC authenticates the timestamp/body, not
event/delivery headers. Deduplicate by signed invoice ID and sequence scoped to your
configured project; an event ID alone is insufficient. Re-fetch the authenticated
invoice, match the order and apply monotonic state/transactional fulfilment.
Do not acknowledge failed storage. Redirects and checkout previews are not proof
of payment. Local tests must never use live invoice writes or wallet credentials.
