"""Receiver building block; verify original HTTP bytes before JSON decoding."""
import json
import re
from whollycrypto import verify_signature

def verified_marketplace_event(raw_body, signature_header, secret, expected_project_ids):
    if not verify_signature(raw_body, signature_header, secret):
        raise ValueError('Invalid or expired signature')
    event=json.loads(raw_body)
    types=["marketplace.invoice.created","marketplace.allocations.available","marketplace.allocations.held","marketplace.payout.approved","marketplace.payout.broadcast","marketplace.payout.confirmed","marketplace.payout.partial","marketplace.payout.failed","marketplace.payout.cancelled","marketplace.refund.prepared","marketplace.refund.confirmed"]
    if (not isinstance(event, dict) or event.get('payload_version') != 1
            or not isinstance(event.get('event_id'), str)
            or not re.fullmatch(r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}', event['event_id'])
            or event.get('project_id') not in expected_project_ids
            or event.get('event_type') not in types or not isinstance(event.get('data'),dict)):
        raise ValueError('Unexpected Marketplace event')
    return event
# Insert authenticated event_id with a UNIQUE constraint and queue work in one
# DB transaction. Return 2xx after durable acceptance; duplicates repeat no action.
# Invoice settlement is not vendor payout confirmation. Do not parse_notification
# these separate envelopes. Never initiate new payouts from callback retries.
