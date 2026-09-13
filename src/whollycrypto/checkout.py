"""Optional public checkout reader. Never stores or sends a merchant API token."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from ._client import JSONClient
from ._validation import uuid_path
from .exceptions import ValidationError
from .http import Transport
from .models import Options, Response


class CheckoutClient:
    def __init__(
        self, checkout_base_url: str, *, options: Options | None = None, transport: Transport | None = None
    ):
        self._http = JSONClient(checkout_base_url, None, options, transport)

    def __enter__(self) -> CheckoutClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def last_response(self) -> Response | None:
        return self._http.last_response

    def get_invoice(self, public_invoice_id: str | UUID) -> dict[str, Any]:
        return self._http.request(
            "GET", "/checkout-api/invoices/" + uuid_path(public_invoice_id), authenticated=False
        )

    def get_preview(self, project_id: str | UUID, store_id: str | UUID | None = None) -> dict[str, Any]:
        query = {} if store_id is None else {"store_id": uuid_path(store_id)}
        return self._http.request(
            "GET", "/checkout-api/previews/" + uuid_path(project_id), query, authenticated=False
        )

    def invoice_url(self, public_invoice_id: str | UUID) -> str:
        """Prefer links.checkout from the API for a live invoice's current domain."""
        return self._http.url("/invoice/" + uuid_path(public_invoice_id))

    def preview_url(
        self, project_id: str | UUID, store_id: str | UUID | None = None, state: str = "waiting"
    ) -> str:
        if state not in ("waiting", "confirming", "paid", "underpaid", "expired"):
            raise ValidationError("Invalid illustrative checkout preview state.")
        return self._http.url(
            "/invoice/preview/" + uuid_path(project_id),
            {"store_id": None if store_id is None else uuid_path(store_id), "state": state},
        )
