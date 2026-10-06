"""Marketplace API for trusted servers, never customer browsers or shipped apps."""
from __future__ import annotations
import re
from typing import Any, Mapping, NoReturn, SupportsIndex
from uuid import UUID
from ._client import JSONClient
from ._validation import decimal_string, uuid_path
from .client import Client
from .exceptions import ValidationError
from .http import Transport
from .models import Options, Response

class MarketplaceClient:
    def __init__(self, base_url: str, api_token: str, *, options: Options | None = None, transport: Transport | None = None):
        if not isinstance(api_token, str) or not re.fullmatch(r"wc_marketplace_[a-f0-9]{32}_[a-f0-9]{64}", api_token):
            raise ValidationError("Use a separate scoped Marketplace API key.")
        self._http = JSONClient(base_url, api_token, options, transport)
    def __repr__(self) -> str:
        return "MarketplaceClient()"
    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError("API clients must not be pickled.")
    def __enter__(self) -> MarketplaceClient:
        return self
    def __exit__(self, *exc) -> None:
        self.close()
    def close(self) -> None:
        self._http.close()
    @property
    def last_response(self) -> Response | None:
        return self._http.last_response
    new_idempotency_key = staticmethod(Client.new_idempotency_key)
    def _scoped(self, project_id: str | UUID, data: Mapping[str, Any] | None) -> dict[str, Any]:
        if data is not None and not isinstance(data, Mapping):
            raise ValidationError("Payload must be a mapping.")
        payload = dict(data or {})
        identity = uuid_path(project_id)
        if "project_id" in payload and payload["project_id"] != identity:
            raise ValidationError("Conflicting project_id.")
        payload["project_id"] = identity
        return payload
    def _read(self, project_id: str | UUID, path: str, filters: Mapping[str, Any] | None) -> dict[str, Any]:
        return self._http.request("GET", path, self._scoped(project_id, filters))
    def _money(self, body: Mapping[str, Any]) -> None:
        for key, value in body.items():
            if value is None:
                continue
            if key in ("amount", "gross_amount", "commission_percent", "exchange_rate_spread_percent", "underpayment_tolerance_percent"):
                decimal_string(value, key)
            if key.endswith("_atomic") and (not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,77})", value)):
                raise ValidationError("Atomic amounts must be exact nonnegative integer strings.")
        for key in ("allocations", "stores"):
            if key in body:
                if not isinstance(body[key], list):
                    raise ValidationError("Expected a list.")
                for row in body[key]:
                    if not isinstance(row, Mapping):
                        raise ValidationError("Expected an object.")
                    self._money(row)
    def _write(self, project_id: str | UUID, path: str, data: Mapping[str, Any], key: str) -> dict[str, Any]:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{16,128}", key):
            raise ValidationError("Persist a 16–128 character idempotency key before sending.")
        payload = self._scoped(project_id, data)
        self._money(payload)
        return self._http.request("POST", path, data=payload, idempotency_key=key)
    def capabilities(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/capabilities; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/capabilities", filters)
    def overview(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/overview; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/overview", filters)
    def settings(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/settings; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/settings", filters)
    def save_settings(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/settings; policies.write."""
        return self._write(project_id, f"/v1/marketplace/settings", data, idempotency_key)
    def list_vendors(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/vendors; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/vendors", filters)
    def create_vendor(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/vendors; vendors.write."""
        return self._write(project_id, f"/v1/marketplace/vendors", data, idempotency_key)
    def get_vendor(self, project_id: str | UUID, vendor_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/vendors/{vendor_id}; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}", filters)
    def update_vendor(self, project_id: str | UUID, vendor_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/vendors/{vendor_id}/update; vendors.write."""
        return self._write(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/update", data, idempotency_key)
    def archive_vendor(self, project_id: str | UUID, vendor_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/vendors/{vendor_id}/archive; vendors.write."""
        return self._write(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/archive", data, idempotency_key)
    def list_destinations(self, project_id: str | UUID, vendor_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/vendors/{vendor_id}/destinations; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/destinations", filters)
    def add_destination(self, project_id: str | UUID, vendor_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/vendors/{vendor_id}/destinations; destinations.write."""
        return self._write(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/destinations", data, idempotency_key)
    def approve_destination(self, project_id: str | UUID, vendor_id: str | UUID, destination_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/vendors/{vendor_id}/destinations/{destination_id}/approve; destinations.approve."""
        return self._write(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/destinations/{uuid_path(destination_id)}/approve", data, idempotency_key)
    def disable_destination(self, project_id: str | UUID, vendor_id: str | UUID, destination_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/vendors/{vendor_id}/destinations/{destination_id}/disable; destinations.approve."""
        return self._write(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/destinations/{uuid_path(destination_id)}/disable", data, idempotency_key)
    def vendor_balances(self, project_id: str | UUID, vendor_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/vendors/{vendor_id}/balances; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/vendors/{uuid_path(vendor_id)}/balances", filters)
    def list_invoices(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/invoices; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/invoices", filters)
    def create_invoice(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/invoices; invoices.write."""
        return self._write(project_id, f"/v1/marketplace/invoices", data, idempotency_key)
    def get_invoice(self, project_id: str | UUID, invoice_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/invoices/{invoice_id}; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}", filters)
    def invoice_payments(self, project_id: str | UUID, invoice_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/invoices/{invoice_id}/payments; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/payments", filters)
    def invoice_allocations(self, project_id: str | UUID, invoice_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/invoices/{invoice_id}/allocations; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/allocations", filters)
    def cancel_invoice(self, project_id: str | UUID, invoice_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/invoices/{invoice_id}/cancel; invoices.write."""
        return self._write(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/cancel", data, idempotency_key)
    def hold_invoice(self, project_id: str | UUID, invoice_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/invoices/{invoice_id}/allocations/hold; reconciliation.write."""
        return self._write(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/allocations/hold", data, idempotency_key)
    def release_invoice(self, project_id: str | UUID, invoice_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/invoices/{invoice_id}/allocations/release; reconciliation.write."""
        return self._write(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/allocations/release", data, idempotency_key)
    def rebind_destination(self, project_id: str | UUID, invoice_id: str | UUID, allocation_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/invoices/{invoice_id}/allocations/{allocation_id}/destination; reconciliation.write."""
        return self._write(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/allocations/{uuid_path(allocation_id)}/destination", data, idempotency_key)
    def refund_invoice(self, project_id: str | UUID, invoice_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/invoices/{invoice_id}/refund; reconciliation.write."""
        return self._write(project_id, f"/v1/marketplace/invoices/{uuid_path(invoice_id)}/refund", data, idempotency_key)
    def allocations(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/allocations; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/allocations", filters)
    def balances(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/balances; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/balances", filters)
    def ledger(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/ledger; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/ledger", filters)
    def list_payouts(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/payouts; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/payouts", filters)
    def preview_payout(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/payouts/preview; payouts.write."""
        return self._write(project_id, f"/v1/marketplace/payouts/preview", data, idempotency_key)
    def create_payout(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/payouts; payouts.write."""
        return self._write(project_id, f"/v1/marketplace/payouts", data, idempotency_key)
    def get_payout(self, project_id: str | UUID, payout_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/payouts/{payout_id}; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/payouts/{uuid_path(payout_id)}", filters)
    def approve_payout(self, project_id: str | UUID, payout_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/payouts/{payout_id}/approve; payouts.approve."""
        return self._write(project_id, f"/v1/marketplace/payouts/{uuid_path(payout_id)}/approve", data, idempotency_key)
    def resume_payout(self, project_id: str | UUID, payout_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/payouts/{payout_id}/resume; payouts.approve."""
        return self._write(project_id, f"/v1/marketplace/payouts/{uuid_path(payout_id)}/resume", data, idempotency_key)
    def cancel_payout(self, project_id: str | UUID, payout_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/payouts/{payout_id}/cancel; payouts.write."""
        return self._write(project_id, f"/v1/marketplace/payouts/{uuid_path(payout_id)}/cancel", data, idempotency_key)
    def list_policies(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/policies; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/policies", filters)
    def save_policy(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/policies; policies.write."""
        return self._write(project_id, f"/v1/marketplace/policies", data, idempotency_key)
    def list_webhooks(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/webhooks; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/webhooks", filters)
    def create_webhook(self, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/webhooks; webhooks.write."""
        return self._write(project_id, f"/v1/marketplace/webhooks", data, idempotency_key)
    def update_webhook(self, project_id: str | UUID, webhook_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/webhooks/{webhook_id}/update; webhooks.write."""
        return self._write(project_id, f"/v1/marketplace/webhooks/{uuid_path(webhook_id)}/update", data, idempotency_key)
    def disable_webhook(self, project_id: str | UUID, webhook_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/webhooks/{webhook_id}/disable; webhooks.write."""
        return self._write(project_id, f"/v1/marketplace/webhooks/{uuid_path(webhook_id)}/disable", data, idempotency_key)
    def list_events(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/events; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/events", filters)
    def get_event(self, project_id: str | UUID, event_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/events/{event_id}; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/events/{uuid_path(event_id)}", filters)
    def list_deliveries(self, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/webhook-deliveries; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/webhook-deliveries", filters)
    def get_delivery(self, project_id: str | UUID, delivery_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET /v1/marketplace/webhook-deliveries/{delivery_id}; marketplace.read."""
        return self._read(project_id, f"/v1/marketplace/webhook-deliveries/{uuid_path(delivery_id)}", filters)
    def resend_delivery(self, project_id: str | UUID, delivery_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        """POST /v1/marketplace/webhook-deliveries/{delivery_id}/resend; webhooks.write."""
        return self._write(project_id, f"/v1/marketplace/webhook-deliveries/{uuid_path(delivery_id)}/resend", data, idempotency_key)
