import json
import pickle
import re
import runpy
import hmac
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from whollycrypto import OperatorClient, OperatorOnboardingClient, Options, APIError, ValidationError, TransportError
from tests.helpers import PROJECT, FakeTransport, reply

TOKEN = 'wc_operator_' + '1' * 32 + '_' + 'a' * 64
KEY = 'saved-operator-request-1042'

class OperatorTests(unittest.TestCase):
    def test_webhook_example_fails_closed(self):
        receive=runpy.run_path(str(Path(__file__).parent.parent / 'examples/operator_webhook.py'))['verified_operator_event']
        body=json.dumps({'event_id':PROJECT,'merchant_id':PROJECT,'event_type':'merchant.created'}).encode()
        stamp=str(int(time.time())); secret='synthetic-operator-hook-secret'
        signature='t='+stamp+',v1='+hmac.new(secret.encode(),stamp.encode()+b'.'+body,'sha256').hexdigest()
        self.assertEqual(receive(body,signature,secret,[PROJECT])['merchant_id'],PROJECT)
        with self.assertRaises(ValueError): receive(body+b' ',signature,secret,[PROJECT])
        with self.assertRaises(ValueError): receive(body,signature,secret,[])
        with self.assertRaises(ValueError): receive(body,signature,'wrong-secret',[PROJECT])

    def test_all_documented_methods(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/operator-v1.json').read_text())
        self.assertEqual(len(fixture['methods']), 55)
        for endpoint in fixture['methods']:
            with self.subTest(method=endpoint['name']):
                transport = FakeTransport(reply(endpoint['response']))
                client = OperatorClient('https://api.example.test', TOKEN, transport=transport)
                name = re.sub(r'[A-Z]', lambda m: '_' + m[0].lower(), endpoint['name'])
                args = [PROJECT for _ in endpoint['ids']]
                if endpoint['method'] == 'POST':
                    args += [endpoint['body'], KEY]
                self.assertEqual(getattr(client, name)(*args), endpoint['response'])
                request = transport.requests[0]
                self.assertEqual(urlsplit(request.url).path, re.sub(r'\{[^}]+\}', PROJECT, endpoint['public_path']))
                self.assertEqual(request.method, endpoint['method'])
                self.assertEqual(request.headers['Authorization'], 'Bearer ' + TOKEN)
                self.assertEqual(request.headers.get('Idempotency-Key'), KEY if endpoint['method'] == 'POST' else None)
                if endpoint['method'] == 'POST':
                    self.assertEqual(json.loads(request.body), endpoint['body'])

    def test_validation_errors_and_retries(self):
        with self.assertRaises(ValidationError):
            OperatorClient('https://api.example.test', 'wc_live_fake')
        transport = FakeTransport()
        client = OperatorClient('https://api.example.test', TOKEN, transport=transport)
        with self.assertRaises(ValidationError): client.create_merchant({}, 'short')
        with self.assertRaises(ValidationError): client.get_merchant('../keys')
        with self.assertRaises(ValidationError): client.adjust_credits(PROJECT, {'amount':1.2}, KEY)
        self.assertEqual(transport.requests, [])
        self.assertNotIn(TOKEN, repr(client))
        with self.assertRaises(TypeError): pickle.dumps(client)
        retry = FakeTransport(TransportError('temporary', retryable=True), reply({'ok':True}))
        OperatorClient('https://api.example.test', TOKEN, options=Options(max_retries=1,max_retry_delay_seconds=0),transport=retry).adjust_credits(PROJECT, {'amount':'-1.20'}, KEY)
        self.assertEqual(retry.requests[0].body, retry.requests[1].body)
        denied = OperatorClient('https://api.example.test', TOKEN, transport=FakeTransport(reply({'error':{'code':'operator_scope_required','message':'Permission required'}},403)))
        with self.assertRaises(APIError) as error: denied.health()
        self.assertEqual(error.exception.error_code,'operator_scope_required')

    def test_token_only_acceptance_is_never_retried(self):
        transport = FakeTransport(reply({'kind':'invitation'}), reply({'password_set':True}))
        client = OperatorOnboardingClient('https://api.example.test', transport=transport)
        client.check_invitation('private-token')
        client.accept_invitation('private-token','private-password', True)
        for request in transport.requests:
            self.assertNotIn('Authorization', request.headers)
            self.assertNotIn('Idempotency-Key', request.headers)
        failed = FakeTransport(reply({},503))
        with self.assertRaises(APIError):
            OperatorOnboardingClient('https://api.example.test',options=Options(max_retries=3),transport=failed).accept_invitation('private-token','private-password',False)
        self.assertEqual(len(failed.requests),1)
