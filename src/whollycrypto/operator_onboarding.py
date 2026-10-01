"""Invitation-token-only API. Never sends an Operator or merchant credential."""
from __future__ import annotations
from typing import Any
from ._client import JSONClient
from .http import Transport
from .models import Options

class OperatorOnboardingClient:
    def __init__(self, api_base_url: str, *, options: Options | None = None, transport: Transport | None = None):
        self._http = JSONClient(api_base_url, None, options, transport)
    def __enter__(self) -> OperatorOnboardingClient:
        return self
    def __exit__(self, *exc) -> None:
        self.close()
    def close(self) -> None:
        self._http.close()
    def check_invitation(self, token: str) -> dict[str, Any]:
        return self._http.request("POST", "/v1/onboarding/invitations/check", data={"token":token}, authenticated=False)
    def accept_invitation(self, token: str, password: str, custody_acknowledged: bool) -> dict[str, Any]:
        """No automatic retry/login. If the response is lost, inspect the link and try signing in."""
        return self._http.request("POST", "/v1/onboarding/invitations/accept", data={"token":token,"password":password,"custody_acknowledged":custody_acknowledged}, authenticated=False)
