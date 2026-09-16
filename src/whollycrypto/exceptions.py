"""Safe exception messages; response bodies are explicit opt-in access."""

from __future__ import annotations

from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from .models import Response


class WhollyCryptoError(Exception):
    """Base SDK error."""


class ValidationError(WhollyCryptoError, ValueError):
    """Invalid local configuration or request. No HTTP request was sent."""


class TransportError(WhollyCryptoError):
    """A network failure; it does not prove an invoice was not created."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class InvalidResponseError(WhollyCryptoError):
    """The API did not return the expected JSON response shape."""


class InvalidSignatureError(WhollyCryptoError):
    """An IPN/webhook signature, clock window or payload is invalid."""


class APIError(WhollyCryptoError):
    """HTTP failure. api_message/response may contain private customer details."""

    def __init__(self, status_code: int, error_code: str, api_message: str | None, response: Response):
        super().__init__(f"Wholly Crypto API request failed (HTTP {status_code}, {error_code})." + _safe_payment_summary(response, error_code))
        self.status_code = status_code
        self.error_code = error_code
        self.api_message = api_message
        self.response = response

    @property
    def retry_after(self) -> int | None:
        return self.response.retry_after_seconds()

    @property
    def details(self) -> dict:
        """Explicit private diagnostics; do not log the complete result by default."""
        return _payment_details(self.response)

    @property
    def payment_method_issues(self) -> list[dict]:
        return _payment_issues(self.response)


def _payment_details(response: Response) -> dict:
    try:
        body = json.loads(response.body)
        error = body.get('error') if isinstance(body, dict) else None
        details = error.get('details') if isinstance(error, dict) else None
        return details if isinstance(details, dict) else {}
    except (ValueError, UnicodeError, RecursionError):
        return {}


def _payment_issues(response: Response) -> list[dict]:
    issues = _payment_details(response).get('payment_methods')
    return [v for v in issues[:64] if isinstance(v, dict)] if isinstance(issues, list) else []


def _safe_payment_summary(response: Response, code: str) -> str:
    if code not in ('invalid_payment_request', 'no_ready_payment_methods', 'payment_rates_unavailable', 'lightning_unavailable'):
        return ''
    # Automatic messages use fixed labels, never remote free text or token tickers.
    chains = {'ethereum':'Ethereum','base':'Base','bnb-chain':'BNB Smart Chain','hyperliquid':'Hyperliquid','bitcoin':'Bitcoin','bitcoin-cash':'Bitcoin Cash','litecoin':'Litecoin','dogecoin':'Dogecoin','zcash':'Zcash','solana':'Solana','tron':'TRON','xrp-ledger':'XRP Ledger','monero':'Monero','cardano':'Cardano','stellar':'Stellar','avalanche':'Avalanche','polygon':'Polygon','arbitrum':'Arbitrum One','optimism':'Optimism','ton':'TON','aptos':'Aptos','sui':'Sui','cosmos':'Cosmos Hub','polkadot':'Polkadot Hub','near':'NEAR','algorand':'Algorand','hedera':'Hedera','kaspa':'Kaspa','tezos':'Tezos','dash':'Dash'}
    reasons = {
        'scanner_provider_quorum':'Two independent scanner-compatible providers are required. Check Settings > Chain connections.',
        'scanner_not_checked':'Scanner checks are missing or stale. Check Settings > Chain connections.',
        'scanner_unavailable':'Receive scanner unavailable. Check Settings > Chain connections.',
        'wallet_missing':'Create the project wallet.', 'wallet_disabled':'Enable the project wallet.',
        'wallet_backup_required':'Back up the project wallet and confirm its backup.',
        'wallet_key_unavailable':'Wallet key unavailable. Check the project wallet configuration.',
        'wallet_activation_required':'Verify on-chain activation of the receiving account.',
        'monero_binding_unavailable':'Verify the view-only Monero wallet connection and backup.',
        'custom_rate_unavailable':'Configure a current custom token price.',
        'rate_unavailable':'A fresh trustworthy exchange rate is unavailable. Check Settings > Rates.',
        'lightning_unavailable':'Check the Lightning connection and project access.',
        'project_disabled':'Enable the project.', 'store_disabled':'Enable the store.',
        'chain_disabled':'Enable the chain in payment methods.', 'asset_disabled':'Enable the asset in payment methods.',
        'asset_not_accepted':'Select an asset accepted by the store.',
    }
    messages = []
    for issue in _payment_issues(response):
        reason, chain, count = issue.get('reason_code'), issue.get('chain_slug'), issue.get('usable_independent_providers')
        if not isinstance(reason, str) or reason not in reasons:
            continue
        label = chains.get(chain, 'Payment method') if isinstance(chain, str) else 'Payment method'
        prefix = f'{count} of 2 independent scanner providers are usable. ' if reason == 'scanner_provider_quorum' and type(count) is int and 0 <= count <= 2 else ''
        message = f'{label}: {prefix}{reasons[reason]}'
        if message not in messages:
            messages.append(message)
    return ' ' + ' '.join(messages[:3]) + (' More payment-method issues are available in payment_method_issues.' if len(messages) > 3 else '') if messages else ''
