"""Public merchant API v1. Methods preserve the complete response envelope."""

from __future__ import annotations

import secrets
from typing import Any, Iterator, Mapping, NoReturn, SupportsIndex
from uuid import UUID

from ._client import JSONClient
from ._validation import decimal_string, uuid_path
from .exceptions import InvalidResponseError, ValidationError
from .http import Transport
from .models import Options, Response


class Client:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        options: Options | None = None,
        transport: Transport | None = None,
    ):
        if api_token is None:
            raise ValidationError("Configure a merchant API token.")
        self._http = JSONClient(base_url, api_token, options, transport)

    def __repr__(self) -> str:
        return "Client(" + repr(self._http) + ")"

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError("API clients containing credentials must not be pickled.")

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned transport. Injected transports remain caller-owned."""
        self._http.close()

    @property
    def last_response(self) -> Response | None:
        return self._http.last_response

    @staticmethod
    def new_idempotency_key() -> str:
        """Generate once; persist with the original invoice payload before sending."""
        return secrets.token_hex(24)

    def service_info(self) -> dict[str, Any]:
        return self._http.request("GET", "/", authenticated=False)

    def health(self) -> dict[str, Any]:
        return self._http.request("GET", "/healthz", authenticated=False)

    def create_invoice(
        self, project_id: str | UUID, store_id: str | UUID, invoice: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        if not isinstance(invoice, Mapping):
            raise ValidationError("invoice must be a mapping.")
        payload = dict(invoice)
        payload["amount"] = decimal_string(payload.get("amount"), "amount")
        for field in ("exchange_rate_spread_percent", "underpayment_tolerance_percent"):
            if payload.get(field) is not None:
                payload[field] = decimal_string(payload[field], field)
        for field in ("metadata", "checkout_appearance"):
            if payload.get(field) is not None and not isinstance(payload[field], Mapping):
                raise ValidationError(field + " must be a JSON object, not a list.")
        if idempotency_key is None:
            raise ValidationError("Invoice creation requires an explicit, persisted idempotency key.")
        return self._http.request(
            "POST",
            self._store(project_id, store_id) + "/invoices",
            data=payload,
            idempotency_key=idempotency_key,
        )

    def get_invoice(self, project_id: str | UUID, public_invoice_id: str | UUID) -> dict[str, Any]:
        return self._http.request(
            "GET", self._project(project_id) + "/invoices/" + uuid_path(public_invoice_id)
        )

    def list_invoices(
        self, project_id: str | UUID, filters: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._http.request("GET", self._project(project_id) + "/invoices", filters)

    def iter_invoices(
        self, project_id: str | UUID, filters: Mapping[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        if filters is not None and not isinstance(filters, Mapping):
            raise ValidationError("filters must be a mapping.")
        query = dict(filters or {})
        offset, limit = query.get("offset", 0), query.get("limit", 50)
        if (
            type(offset) is not int
            or not 0 <= offset <= 1_000_000
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ValidationError("Invalid invoice pagination limit or offset.")
        while True:
            page = self.list_invoices(project_id, {**query, "offset": offset, "limit": limit})
            rows, pagination = page.get("data"), page.get("pagination")
            if (
                not isinstance(rows, list)
                or not isinstance(pagination, dict)
                or type(pagination.get("offset")) is not int
                or pagination["offset"] != offset
                or type(pagination.get("limit")) is not int
                or pagination["limit"] != limit
                or type(pagination.get("has_more")) is not bool
            ):
                raise InvalidResponseError("Invoice response has invalid pagination metadata.")
            for row in rows:
                if not isinstance(row, dict):
                    raise InvalidResponseError("Invoice list contains an invalid item.")
                yield row
            if not pagination["has_more"]:
                return
            if not rows or offset + limit > 1_000_000:
                raise InvalidResponseError("Invoice pagination cannot advance safely.")
            offset += limit

    def list_project_payment_assets(self, project_id: str | UUID) -> dict[str, Any]:
        return self._http.request("GET", self._project(project_id) + "/payment-assets")

    def update_project_payment_asset(
        self, project_id: str | UUID, asset_id: str | UUID, policy: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self._http.request(
            "PUT", self._project(project_id) + "/payment-assets/" + uuid_path(asset_id), data=policy
        )

    def list_token_candidates(
        self, project_id: str | UUID, chain_slug: str, filters: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if filters is not None and not isinstance(filters, Mapping):
            raise ValidationError("filters must be a mapping.")
        return self._http.request(
            "GET",
            self._project(project_id) + "/payment-token-candidates",
            {**(filters or {}), "chain_slug": chain_slug},
        )

    def register_token_asset(self, project_id: str | UUID, token: Mapping[str, Any]) -> dict[str, Any]:
        return self._http.request("POST", self._project(project_id) + "/payment-token-assets", data=token)

    def discover_custom_dex_pools(
        self, project_id: str | UUID, chain_slug: str, contract_address: str
    ) -> dict[str, Any]:
        return self._http.request(
            "GET",
            self._project(project_id) + "/payment-token-dex-pools",
            {"chain_slug": chain_slug, "contract_address": contract_address},
        )

    def register_custom_token(self, project_id: str | UUID, token: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(token, Mapping):
            raise ValidationError("token must be a mapping.")
        payload = dict(token)
        if payload.get("price_usd") is not None:
            payload["price_usd"] = decimal_string(payload["price_usd"], "price_usd")
        return self._http.request(
            "POST", self._project(project_id) + "/payment-token-assets/custom", data=payload
        )

    def list_store_payment_assets(self, project_id: str | UUID, store_id: str | UUID) -> dict[str, Any]:
        return self._http.request("GET", self._store(project_id, store_id) + "/payment-assets")

    def update_store_payment_assets(
        self, project_id: str | UUID, store_id: str | UUID, assets: list[Mapping[str, Any]]
    ) -> dict[str, Any]:
        """REPLACE the entire on-chain selection. [] clears it; does not configure Lightning."""
        if not isinstance(assets, list):
            raise ValidationError("assets must be a list of asset_id/display_order objects.")
        return self._http.request(
            "PUT", self._store(project_id, store_id) + "/payment-assets", data={"assets": assets}
        )

    def update_store_confirmation_policy(
        self, project_id: str | UUID, store_id: str | UUID, asset_id: str | UUID, policy: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self._http.request(
            "PUT",
            self._store(project_id, store_id)
            + "/payment-assets/"
            + uuid_path(asset_id)
            + "/confirmation-policy",
            data=policy,
        )

    def list_project_wallets(self, project_id: str | UUID) -> dict[str, Any]:
        """Public addresses and balances only. No private keys, recovery words or spending."""
        return self._http.request("GET", self._project(project_id) + "/wallets")

    def list_reconciliation(
        self, project_id: str | UUID, filters: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._http.request("GET", self._project(project_id) + "/reconciliation", filters)

    def get_reconciliation(
        self, project_id: str | UUID, public_invoice_id: str | UUID, page: int = 1
    ) -> dict[str, Any]:
        return self._http.request(
            "GET",
            self._project(project_id) + "/reconciliation/" + uuid_path(public_invoice_id),
            {"page": page},
        )

    @staticmethod
    def _project(project_id: str | UUID) -> str:
        return "/v1/projects/" + uuid_path(project_id)

    @classmethod
    def _store(cls, project_id: str | UUID, store_id: str | UUID) -> str:
        return cls._project(project_id) + "/stores/" + uuid_path(store_id)
