import json
import re
import pickle
import runpy
import hmac
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from whollycrypto import MarketplaceClient, ValidationError
from tests.helpers import PROJECT, FakeTransport, reply

TOKEN='wc_marketplace_'+'1'*32+'_'+'a'*64
KEY='saved-marketplace-request-1042'

class MarketplaceTests(unittest.TestCase):
    def test_all_routes(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/marketplace-v1.json').read_text())
        self.assertEqual(len(fixture['methods']),45)
        for e in fixture['methods']:
            with self.subTest(method=e['name']):
                transport=FakeTransport(reply(e['response']))
                c=MarketplaceClient('https://api.example.test',TOKEN,transport=transport)
                args=[PROJECT]+[PROJECT for _ in e['ids']]
                body={**e['body'],'project_id':PROJECT} if e['body'] else None
                args += [body,KEY] if e['method']=='POST' else [{'page':2}]
                name=re.sub(r'[A-Z]',lambda m:'_'+m[0].lower(),e['name'])
                self.assertEqual(getattr(c,name)(*args),e['response'])
                request=transport.requests[0];url=urlsplit(request.url)
                self.assertEqual(request.method,e['method'])
                self.assertEqual(url.path,re.sub(r'\{[^}]+\}',PROJECT,e['public_path']))
                self.assertEqual(request.headers['Authorization'],'Bearer '+TOKEN)
                if body:
                    self.assertEqual(json.loads(request.body),body)
                    self.assertEqual(request.headers['Idempotency-Key'],KEY)
                else:
                    self.assertEqual(parse_qs(url.query)['project_id'],[PROJECT])
                    self.assertEqual(parse_qs(url.query)['page'],['2'])
    def test_validation_before_transport(self):
        with self.assertRaises(ValidationError):MarketplaceClient('https://api.example.test','wc_live_fake')
        t=FakeTransport();c=MarketplaceClient('https://api.example.test',TOKEN,transport=t)
        with self.assertRaises(ValidationError):c.create_invoice(PROJECT,{'amount':0.1},KEY)
        with self.assertRaises(ValidationError):c.create_invoice(PROJECT,{'allocations':[{'gross_amount':1}]},KEY)
        with self.assertRaises(ValidationError):c.create_payout(PROJECT,{'maximum_network_fee_atomic':10000},KEY)
        with self.assertRaises(ValidationError):c.list_vendors(PROJECT,{'project_id':'wrong'})
        with self.assertRaises(ValidationError):c.get_vendor(PROJECT,'../keys')
        with self.assertRaises(ValidationError):c.create_vendor(PROJECT,{},'short')
        with self.assertRaises(TypeError):pickle.dumps(c)
        self.assertNotIn(TOKEN,repr(c));self.assertEqual(t.requests,[])
    def test_signed_events(self):
        receive=runpy.run_path(str(Path(__file__).parent.parent/'examples/marketplace_webhook.py'))['verified_marketplace_event']
        raw=json.dumps({'payload_version':1,'event_id':PROJECT,'project_id':PROJECT,'event_type':'marketplace.payout.confirmed','data':{'payout_id':PROJECT}}).encode()
        stamp=str(int(time.time()));secret='synthetic-marketplace-hook-secret'
        sig='t='+stamp+',v1='+hmac.new(secret.encode(),stamp.encode()+b'.'+raw,'sha256').hexdigest()
        self.assertEqual(receive(raw,sig,secret,[PROJECT])['data']['payout_id'],PROJECT)
        with self.assertRaises(ValueError):receive(raw,sig,secret,[])
        with self.assertRaises(ValueError):receive(raw+b' ',sig,secret,[PROJECT])
