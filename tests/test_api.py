import copy
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import HTTPServer
from decimal import Decimal

from uta.api import Handler, SAMPLE, evaluate


class APITests(unittest.TestCase):
    def test_risk_sample_and_order_check(self):
        risk = evaluate('/risk', SAMPLE)
        self.assertEqual(Decimal(risk['equity']), Decimal('1100'))
        self.assertEqual(Decimal(risk['initial_margin']), Decimal('210'))
        self.assertEqual(Decimal(risk['maintenance_margin']), Decimal('105'))
        request = dict(SAMPLE, order={'symbol': 'BTC-PERP', 'quantity': '1', 'execution_price': '21000'})
        result = evaluate('/order-check', request)
        self.assertFalse(result['accepted'])

    def test_input_missing_specs_and_numeric_precision_fail_closed(self):
        request = copy.deepcopy(SAMPLE)
        request['balances']['USD'] = 1000.0
        with self.assertRaises(ValueError):
            evaluate('/risk', request)
        request = copy.deepcopy(SAMPLE)
        request['instruments'] = {}
        with self.assertRaises(ValueError):
            evaluate('/risk', request)

    def test_real_http_json_success_and_bad_request(self):
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        self.addCleanup(connection.close)
        connection.request('GET', '/health')
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertFalse(json.loads(response.read())['trading_enabled'])
        body = json.dumps(SAMPLE)
        connection.request('POST', '/risk', body=body, headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(Decimal(json.loads(response.read())['equity']), Decimal('1100'))
        connection.request('POST', '/risk', body='{}', headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        self.assertIn('error', json.loads(response.read()))


if __name__ == '__main__':
    unittest.main()
