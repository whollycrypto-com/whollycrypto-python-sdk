# Payment methods and reconciliation

Use an open client as shown in the README. Project, store and asset arguments use
API UUIDs. Token registration runs live chain checks; use
`Options(timeout_seconds=60)` and ensure your reverse proxy allows that timeout.
If registration times out, check the asset list before trying again.

## Catalog tokens

```python
candidates = client.list_token_candidates(project_id, "ethereum", {"q": "USDC", "limit": 20})
result = client.register_token_asset(project_id, {
    "chain_slug": "ethereum", "coingecko_id": "usd-coin", "enabled": True,
})
asset_id = result["data"]["asset_id"]
```

A catalog match is discovery, not payment readiness. The server verifies on-chain
metadata, scanner support, project access and wallet readiness.

## Custom tokens and prices

```python
pools = client.discover_custom_dex_pools(project_id, "ethereum", contract_address)
result = client.register_custom_token(project_id, {
    "chain_slug": "ethereum", "contract_address": contract_address,
    "name": "Example token", "symbol": "EXAMPLE", "price_usd": "0.25",
})

# Or choose a pool returned by discovery and omit price_usd:
result = client.register_custom_token(project_id, {
    "chain_slug": "ethereum", "contract_address": contract_address,
    "name": "Example token", "symbol": "EXAMPLE",
    "price_mode": "dex", "dex_pair_address": chosen_pool_address,
})
```

Do not identify a contract only by ticker or assume a pool has safe liquidity.
The merchant rechecks the pool and applies its current pricing rules.

## Store acceptance and confirmations

```python
current = client.list_store_payment_assets(project_id, store_id)

# ENTIRE desired on-chain selection, not an append operation:
client.update_store_payment_assets(project_id, store_id, [
    {"asset_id": bitcoin_asset_id, "display_order": 0},
    {"asset_id": usdc_asset_id, "display_order": 1},
])
client.update_store_confirmation_policy(project_id, store_id, bitcoin_asset_id, {
    "strategy": "custom", "required_confirmations": 2,
})
# Restore inherited project policy:
client.update_store_confirmation_policy(project_id, store_id, bitcoin_asset_id, {"strategy": "inherit"})
```

`[]` removes all on-chain selections. Lightning is managed separately in the console
and its readiness is returned in `lightning`. Zero confirmations permits settlement
on detection and carries greater reversal/double-spend risk. Finality-only chains
may reject editable confirmation counts.

## Invoice-specific selection

On merchant 5.3.0+, select already accepted tokens with `chain_slug` and
`asset_tickers`, for example `{"chain_slug":"ethereum","asset_tickers":["USDC","USDT"]}`.
Find the chain hint and asset ticker in **Project → Stores → Payment methods**.
Put your selection in `payment_methods`. Tickers are case-insensitive and chain-scoped.
They never enable new store assets. Duplicate accepted symbols are rejected;
use `asset_ids` with the selected entry's `asset.id` for an exact contract instead.
Do not send both selectors. Omit both to include all active accepted assets on that chain.
Merchant 5.4.0+ ignores unknown, inactive or unaccepted choices and uses store
defaults if none match. Active selected assets still need ready wallets/scanners
and trustworthy rates. Older merchants reject unmatched choices. Check the API
error message and details.payment_methods for chain-specific diagnostics.
See the [complete invoice example](../README.md#choose-invoice-payment-methods).

## Receiving diagnostics

Merchant 5.5.0+ includes `receive_readiness` in scoped asset and wallet listings.
It describes cached receiving requirements, not balances or sending/gas checks.
Invoice creation rechecks requirements and rates for its currency. A healthy
TRON full node alone is not a history indexer for payment discovery.

SDK 2.4.0+ gives `str(APIError)` a safe, actionable summary. Inspect
`error.payment_method_issues` for structured chain, ticker, reason code and
provider requirements, or `error.details` for the full details object.
Treat explicit server details as untrusted data: escape before rendering and
do not log full responses or customer data. Fix the named configuration, then
retry with the **same idempotency key**. Never disable scanner checks.

## Balances and exceptions

```python
wallets = client.list_project_wallets(project_id)["data"]
for wallet in wallets:
    for balance in wallet["balances"]:
        # Keep balance and balance_atomic exact. Inspect status/checked_at.
        # Pending, stale or unavailable values are not a zero balance.
        pass

queue = client.list_reconciliation(project_id, {
    "status": "open", "reason": "underpaid", "page": 1,
})
detail = client.get_reconciliation(project_id, public_invoice_id, page=2)
```

The detail's `page` selects decision history only. Wallet responses contain public
addresses and balances, not secrets. Refunds, sends, cancellation and reconciliation
decisions remain controlled console actions, not SDK mutations.
