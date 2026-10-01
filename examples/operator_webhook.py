"""Receiver building block: integrate with your HTTPS endpoint and durable queue."""
import json
import re
from whollycrypto import verify_signature

def verified_operator_event(raw_body, signature_header, secret, expected_merchant_ids):
    if not verify_signature(raw_body, signature_header, secret):
        raise ValueError('Invalid or expired signature')
    event = json.loads(raw_body)
    events = {'merchant.created', 'merchant.updated', 'user.created', 'user.updated',
              'invitation.accepted', 'password_reset.completed', 'topup.settled', 'credit.balance_changed'}
    if (not isinstance(event, dict) or not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', str(event.get('event_id', '')))
            or event.get('merchant_id') not in expected_merchant_ids or event.get('event_type') not in events):
        raise ValueError('Unexpected Operator event')
    return event
# Transactionally insert a unique event_id and enqueue reconciliation. Duplicates
# receive 2xx without repeating actions; acknowledge only after durable storage.
# Do not use the invoice-notification parser: these are separate lifecycle events.
