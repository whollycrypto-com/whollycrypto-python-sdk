# Operator API

Requires Wholly Crypto 7.4.0+, an installation permanently set to Operator mode, and opt-in under Operator → Settings → Operator API. Use the **API hostname**, with a separate scoped `wc_operator_` key kept on your server. Ordinary merchant keys cannot manage tenants.

[Full Operator API reference](https://www.whollycrypto.com/api/#operator-api) · [Create merchant fields](https://www.whollycrypto.com/api/#operator-create-merchant)

Choose direct onboarding with a password, or invitation onboarding without a password. Direct users must acknowledge hosted-wallet custody at first login; temporary passwords can require a change. Invitation acceptance sets a password but never logs in or bypasses Basic Auth/TOTP. Only set custody acknowledgement after the person has actually agreed.

Every Operator POST requires a persisted 16–128 character idempotency key. Keep the same key and exact body after a timeout. Secrets and private links are shown only on the first successful response; replay returns a redacted receipt. An interrupted request returns `operator_request_in_progress`: inspect resources/audit instead of blindly submitting a new key. Persist request IDs for credit adjustments/top-ups too. A local credit grant does not refill the installation's own credit balance.

Default key quota: 60/minute, configurable 1–600. Honour Retry-After on 429. Scope/IP/expiry/tenant checks apply to every request. There are no public wallet-secret, spending, refund, destructive deletion, TOTP-reset or server-configuration operations.

Operator webhooks are **not invoice callbacks**. Use the generic signature verifier over the raw body and Wholly-Signature, then validate merchant_id/event_type and transactionally deduplicate event_id. Do not feed them into the invoice-notification parser. Subscriptions belong to their issuing credential. Deliveries are at least once, may be out of order, retry up to 8 attempts and retain history for 30 days. Return 2xx only after durable acceptance; reconcile against current resources. Do not use a lifecycle event alone to fulfil a customer's order.

## Methods

| Method | HTTP | Path |
| --- | --- | --- |
| `capabilities` | GET | `/v1/operator/capabilities` |
| `health` | GET | `/v1/operator/health` |
| `list_merchants` | GET | `/v1/operator/merchants` |
| `create_merchant` | POST | `/v1/operator/merchants` |
| `get_merchant` | GET | `/v1/operator/merchants/{merchant_id}` |
| `update_merchant` | POST | `/v1/operator/merchants/{merchant_id}` |
| `list_users` | GET | `/v1/operator/merchants/{merchant_id}/users` |
| `create_user` | POST | `/v1/operator/merchants/{merchant_id}/users` |
| `get_user` | GET | `/v1/operator/merchants/{merchant_id}/users/{user_id}` |
| `update_user` | POST | `/v1/operator/merchants/{merchant_id}/users/{user_id}` |
| `set_user_password` | POST | `/v1/operator/merchants/{merchant_id}/users/{user_id}/password` |
| `revoke_user_sessions` | POST | `/v1/operator/merchants/{merchant_id}/users/{user_id}/revoke-sessions` |
| `list_invitations` | GET | `/v1/operator/merchants/{merchant_id}/invitations` |
| `create_invitation` | POST | `/v1/operator/merchants/{merchant_id}/invitations` |
| `get_invitation` | GET | `/v1/operator/invitations/{invitation_id}` |
| `resend_invitation` | POST | `/v1/operator/invitations/{invitation_id}/resend` |
| `revoke_invitation` | POST | `/v1/operator/invitations/{invitation_id}/revoke` |
| `get_credits` | GET | `/v1/operator/merchants/{merchant_id}/credits` |
| `list_credit_ledger` | GET | `/v1/operator/merchants/{merchant_id}/credits/ledger` |
| `adjust_credits` | POST | `/v1/operator/merchants/{merchant_id}/credits/adjustments` |
| `list_topups` | GET | `/v1/operator/merchants/{merchant_id}/topups` |
| `create_topup` | POST | `/v1/operator/merchants/{merchant_id}/topups` |
| `get_topup` | GET | `/v1/operator/merchants/{merchant_id}/topups/{topup_id}` |
| `reports` | GET | `/v1/operator/reports` |
| `list_audit` | GET | `/v1/operator/audit` |
| `list_events` | GET | `/v1/operator/events` |
| `list_webhooks` | GET | `/v1/operator/webhooks` |
| `create_webhook` | POST | `/v1/operator/webhooks` |
| `update_webhook` | POST | `/v1/operator/webhooks/{webhook_id}` |
| `rotate_webhook_secret` | POST | `/v1/operator/webhooks/{webhook_id}/rotate` |
| `list_webhook_deliveries` | GET | `/v1/operator/webhooks/{webhook_id}/deliveries` |
| `list_projects` | GET | `/v1/operator/merchants/{merchant_id}/projects` |
| `create_project` | POST | `/v1/operator/merchants/{merchant_id}/projects` |
| `get_project` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}` |
| `update_project` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}` |
| `list_stores` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores` |
| `create_store` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores` |
| `get_store` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}` |
| `update_store` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}` |
| `get_store_appearance` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/checkout-appearance` |
| `update_store_appearance` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/checkout-appearance` |
| `list_store_payment_assets` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/payment-assets` |
| `update_store_payment_assets` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/payment-assets` |
| `list_store_webhooks` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/webhooks` |
| `create_store_webhook` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/webhooks` |
| `update_store_webhook` | POST | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/stores/{store_id}/webhooks/{webhook_id}` |
| `list_invoices` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/invoices` |
| `get_invoice` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/invoices/{invoice_id}` |
| `list_wallets` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/wallets` |
| `list_wallet_addresses` | GET | `/v1/operator/merchants/{merchant_id}/projects/{project_id}/wallets/{wallet_id}/addresses` |
| `list_merchant_credentials` | GET | `/v1/operator/merchants/{merchant_id}/api-credentials` |
| `create_merchant_credential` | POST | `/v1/operator/merchants/{merchant_id}/api-credentials` |
| `update_merchant_credential` | POST | `/v1/operator/merchants/{merchant_id}/api-credentials/{credential_id}` |
| `rotate_merchant_credential` | POST | `/v1/operator/merchants/{merchant_id}/api-credentials/{credential_id}/rotate` |
| `revoke_merchant_credential` | POST | `/v1/operator/merchants/{merchant_id}/api-credentials/{credential_id}/revoke` |

Token-only onboarding uses the separate `OperatorOnboardingClient`: `check_invitation(token)` and `accept_invitation(token, password, custody_acknowledged)`. No Operator key is sent. See the adjacent examples; they are templates, never run them against a production installation without reviewing the changes.
