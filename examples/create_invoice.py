"""Opt-in example: running this creates a real invoice on YOUR configured merchant API.

Persist the order payload and idempotency key before running. Never print the token.
Variable example: amount = "25.00", then "amount": str(amount).
Keep decimal input as a string or Decimal; str(float) cannot recover lost precision.
"""

import os

from whollycrypto import Client


def main() -> None:
    # Configuration comes only from your server, never a customer-supplied URL.
    with Client(os.environ["WHOLLY_API_URL"], os.environ["WHOLLY_API_TOKEN"]) as client:
        result = client.create_invoice(
            os.environ["WHOLLY_PROJECT_ID"],
            os.environ["WHOLLY_STORE_ID"],
            {"amount": "49.90", "currency": "EUR", "order_id": "order-1042"},
            os.environ["WHOLLY_ORDER_IDEMPOTENCY_KEY"],
        )
        print(result["links"]["checkout"])


if __name__ == "__main__":
    main()
