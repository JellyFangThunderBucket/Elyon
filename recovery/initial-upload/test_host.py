import json
import multiprocessing
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from elyon.cli import Client, serve


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.endpoint = root / 'endpoint.json'
        self.process = multiprocessing.get_context('spawn').Process(
            target=serve, args=(root / 'journal', self.endpoint, 0))
        self.process.start()
        deadline = time.monotonic() + 10
        while not self.endpoint.exists() and self.process.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.client = Client(self.endpoint)

    def tearDown(self):
        self.process.terminate()
        self.process.join(5)
        self.tmp.cleanup()

    def test_control_process_serves_snapshot_without_content(self):
        self.assertEqual(self.client.send('hello')['type'], 'capabilities')
        self.assertEqual(self.client.send('snapshot')['graph']['nodes'], [])

    def test_missing_token_and_cross_origin_mutation_are_rejected(self):
        endpoint = json.loads(self.endpoint.read_text())
        for headers in [{}, {'Authorization': 'Bearer ' + endpoint['token'],
                             'Origin': 'https://attacker.test'}]:
            request = urllib.request.Request(endpoint['url'], data=b'{}', headers=headers)
            with self.subTest(headers=list(headers)), self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(e.exception.code, 403)

    def test_oversized_body_and_malformed_message_are_rejected(self):
        endpoint = json.loads(self.endpoint.read_text())
        for payload, status in [(b'x' * 262145, 413), (b'[]', 400), (b'{bad', 400)]:
            request = urllib.request.Request(endpoint['url'], data=payload,
                headers={'Authorization': 'Bearer ' + endpoint['token']})
            with self.subTest(status=status), self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(e.exception.code, status)
        self.assertEqual(self.client.send('snapshot')['graph']['nodes'], [])


if __name__ == '__main__':
    unittest.main()
