import json

from whollycrypto import Response

PROJECT = "11111111-1111-4111-8111-111111111111"
STORE = "22222222-2222-4222-8222-222222222222"
INVOICE = "33333333-3333-4333-8333-333333333333"
ASSET = "44444444-4444-4444-8444-444444444444"
TOKEN = "wc_fixture_not_a_real_credential"


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.closed = False

    def send(self, request, options):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("Unexpected extra HTTP request")
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def close(self):
        self.closed = True


def reply(data=None, status=200, headers=None):
    return Response(
        status,
        {"Content-Type": "application/json", **(headers or {})},
        json.dumps({"data": []} if data is None else data).encode(),
    )


def invoke(client, endpoint, body):
    calls = {
        "api-service-root": lambda: client.service_info(),
        "api-health": lambda: client.health(),
        "reconciliation-list": lambda: client.list_reconciliation(PROJECT, {"status": "open", "page": 1}),
        "reconciliation-detail": lambda: client.get_reconciliation(PROJECT, INVOICE),
        "list-project-payment-assets": lambda: client.list_project_payment_assets(PROJECT),
        "update-project-payment-asset": lambda: client.update_project_payment_asset(PROJECT, ASSET, body),
        "list-token-candidates": lambda: client.list_token_candidates(
            PROJECT, "ethereum", {"q": "usd", "limit": 10}
        ),
        "register-token-asset": lambda: client.register_token_asset(PROJECT, body),
        "discover-custom-dex-pools": lambda: client.discover_custom_dex_pools(
            PROJECT, "ethereum", "0x" + "1" * 40
        ),
        "register-custom-token": lambda: client.register_custom_token(PROJECT, body),
        "list-store-payment-assets": lambda: client.list_store_payment_assets(PROJECT, STORE),
        "update-store-payment-assets": lambda: client.update_store_payment_assets(
            PROJECT, STORE, body["assets"]
        ),
        "update-store-confirmation-policy": lambda: client.update_store_confirmation_policy(
            PROJECT, STORE, ASSET, body
        ),
        "list-project-wallets": lambda: client.list_project_wallets(PROJECT),
        "create-invoice": lambda: client.create_invoice(PROJECT, STORE, body, "persisted-order-1042"),
        "list-invoices": lambda: client.list_invoices(
            PROJECT, {"search": "order-1042", "limit": 50, "offset": 0}
        ),
        "get-invoice": lambda: client.get_invoice(PROJECT, INVOICE),
        "list-invoice-payments": lambda: client.list_invoice_payments(PROJECT, INVOICE, {"limit": 25, "offset": 0}),
    }
    return calls[endpoint]()
