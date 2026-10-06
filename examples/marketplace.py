"""Trusted backend only. Importing this module never sends requests or funds."""
from whollycrypto import MarketplaceClient


def marketplace_invoice(client: MarketplaceClient, project_id: str, store_id: str,
                        vendor_ids: list[str], saved_key: str) -> dict:
    if len(vendor_ids) != 3:
        raise ValueError("Use three approved vendors")
    return client.create_invoice(project_id, {
        "store_id": store_id, "amount": "300.00", "currency": "USD",
        # A variable may use str(amount) from Decimal/user input, not float math.
        "order_id": "marketplace-cart-1042",
        "allocations": [{"vendor_id": v, "gross_amount": "100.00"} for v in vendor_ids],
    }, saved_key)  # Persist the key/body first; reuse on timeout.
    # Save data.invoice_id and redirect to TOP-LEVEL links.checkout.


def prepare_marketplace_payout(client: MarketplaceClient, project_id: str,
                               allocation_ids: list[str], fee_cap_atomic: str,
                               gas_cap_atomic: str, saved_key: str) -> dict:
    # One asset; for BTC include every unpaid share of each selected invoice.
    # Caps use native-coin atomic units. Preparation does NOT send funds.
    return client.create_payout(project_id, {
        "allocation_ids": allocation_ids, "maximum_network_fee_atomic": fee_cap_atomic,
        "maximum_gas_funding_atomic": gas_cap_atomic,
    }, saved_key)

# Inspect get_payout() recipients, amounts, revision and plan_hash first.
# Only after explicit authorization:
# client.approve_payout(project_id, payout_id, {
#     "revision": reviewed_revision, "expected_plan_hash": reviewed_hash, "confirm": True,
# }, separately_persisted_approval_key)
# Follow get_payout() to state=paid, not merely broadcast.
