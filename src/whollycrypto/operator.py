"""Server-side Operator API; credentials and tenant scopes are separate from merchant API keys."""
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

class OperatorClient:
    def __init__(self, base_url: str, api_token: str, *, options: Options | None = None, transport: Transport | None = None):
        if not isinstance(api_token, str) or not re.fullmatch(r"wc_operator_[a-f0-9]{32}_[a-f0-9]{64}", api_token):
            raise ValidationError("Configure a separate Operator API key, not a merchant key.")
        self._http = JSONClient(base_url, api_token, options, transport)
    def __repr__(self) -> str:
        return "OperatorClient()"
    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError("API clients must not be pickled.")
    def __enter__(self) -> OperatorClient:
        return self
    def __exit__(self, *exc) -> None:
        self.close()
    def close(self) -> None:
        self._http.close()
    @property
    def last_response(self) -> Response | None:
        return self._http.last_response
    new_idempotency_key = staticmethod(Client.new_idempotency_key)
    def _write(self, path: str, data: Mapping[str, Any], key: str) -> dict[str, Any]:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{16,128}", key):
            raise ValidationError("Persist a 16–128 character idempotency key before sending.")
        if not isinstance(data, Mapping):
            raise ValidationError("Payload must be a mapping.")
        payload = dict(data)
        for field in ("amount", "starting_credit"):
            if payload.get(field) is not None:
                value = payload[field]
                negative = field == "amount" and path.endswith("/credits/adjustments") and isinstance(value, str) and value.startswith("-")
                payload[field] = ("-" if negative else "") + decimal_string(value[1:] if negative else value, field)
        return self._http.request("POST", path, data=payload, idempotency_key=key)
    def capabilities(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/capabilities", filters)
    def health(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/health", filters)
    def list_merchants(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants", filters)
    def create_merchant(self, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants", data, idempotency_key)
    def get_merchant(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}", filters)
    def update_merchant(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}", data, idempotency_key)
    def list_users(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/users", filters)
    def create_user(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/users", data, idempotency_key)
    def get_user(self, merchant_id: str | UUID, user_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/users/{uuid_path(user_id)}", filters)
    def update_user(self, merchant_id: str | UUID, user_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/users/{uuid_path(user_id)}", data, idempotency_key)
    def set_user_password(self, merchant_id: str | UUID, user_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/users/{uuid_path(user_id)}/password", data, idempotency_key)
    def revoke_user_sessions(self, merchant_id: str | UUID, user_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/users/{uuid_path(user_id)}/revoke-sessions", data, idempotency_key)
    def list_invitations(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/invitations", filters)
    def create_invitation(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/invitations", data, idempotency_key)
    def get_invitation(self, invitation_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/invitations/{uuid_path(invitation_id)}", filters)
    def resend_invitation(self, invitation_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/invitations/{uuid_path(invitation_id)}/resend", data, idempotency_key)
    def revoke_invitation(self, invitation_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/invitations/{uuid_path(invitation_id)}/revoke", data, idempotency_key)
    def get_credits(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/credits", filters)
    def list_credit_ledger(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/credits/ledger", filters)
    def adjust_credits(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/credits/adjustments", data, idempotency_key)
    def list_topups(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/topups", filters)
    def create_topup(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/topups", data, idempotency_key)
    def get_topup(self, merchant_id: str | UUID, topup_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/topups/{uuid_path(topup_id)}", filters)
    def reports(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/reports", filters)
    def list_audit(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/audit", filters)
    def list_events(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/events", filters)
    def list_webhooks(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/webhooks", filters)
    def create_webhook(self, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/webhooks", data, idempotency_key)
    def update_webhook(self, webhook_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/webhooks/{uuid_path(webhook_id)}", data, idempotency_key)
    def rotate_webhook_secret(self, webhook_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/webhooks/{uuid_path(webhook_id)}/rotate", data, idempotency_key)
    def list_webhook_deliveries(self, webhook_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/webhooks/{uuid_path(webhook_id)}/deliveries", filters)
    def list_projects(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects", filters)
    def create_project(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects", data, idempotency_key)
    def get_project(self, merchant_id: str | UUID, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}", filters)
    def update_project(self, merchant_id: str | UUID, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}", data, idempotency_key)
    def list_stores(self, merchant_id: str | UUID, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores", filters)
    def create_store(self, merchant_id: str | UUID, project_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores", data, idempotency_key)
    def get_store(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}", filters)
    def update_store(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}", data, idempotency_key)
    def get_store_appearance(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/checkout-appearance", filters)
    def update_store_appearance(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/checkout-appearance", data, idempotency_key)
    def list_store_payment_assets(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/payment-assets", filters)
    def update_store_payment_assets(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/payment-assets", data, idempotency_key)
    def list_store_webhooks(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/webhooks", filters)
    def create_store_webhook(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/webhooks", data, idempotency_key)
    def update_store_webhook(self, merchant_id: str | UUID, project_id: str | UUID, store_id: str | UUID, webhook_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/stores/{uuid_path(store_id)}/webhooks/{uuid_path(webhook_id)}", data, idempotency_key)
    def list_invoices(self, merchant_id: str | UUID, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/invoices", filters)
    def get_invoice(self, merchant_id: str | UUID, project_id: str | UUID, invoice_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/invoices/{uuid_path(invoice_id)}", filters)
    def list_wallets(self, merchant_id: str | UUID, project_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/wallets", filters)
    def list_wallet_addresses(self, merchant_id: str | UUID, project_id: str | UUID, wallet_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/projects/{uuid_path(project_id)}/wallets/{uuid_path(wallet_id)}/addresses", filters)
    def list_merchant_credentials(self, merchant_id: str | UUID, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._http.request("GET", f"/v1/operator/merchants/{uuid_path(merchant_id)}/api-credentials", filters)
    def create_merchant_credential(self, merchant_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/api-credentials", data, idempotency_key)
    def update_merchant_credential(self, merchant_id: str | UUID, credential_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/api-credentials/{uuid_path(credential_id)}", data, idempotency_key)
    def rotate_merchant_credential(self, merchant_id: str | UUID, credential_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/api-credentials/{uuid_path(credential_id)}/rotate", data, idempotency_key)
    def revoke_merchant_credential(self, merchant_id: str | UUID, credential_id: str | UUID, data: Mapping[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._write(f"/v1/operator/merchants/{uuid_path(merchant_id)}/api-credentials/{uuid_path(credential_id)}/revoke", data, idempotency_key)
