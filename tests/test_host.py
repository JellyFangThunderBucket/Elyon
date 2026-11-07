import json
import multiprocessing
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from elyon.cli import Client, serve


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.endpoint = root / "endpoint.json"
        self.process = multiprocessing.get_context("spawn").Process(
            target=serve, args=(root / "journal", self.endpoint, 0)
        )
        self.process.start()
        deadline = time.monotonic() + 10
        while (
            not self.endpoint.exists() and self.process.is_alive() and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        self.client = Client(self.endpoint)

    def tearDown(self):
        self.process.terminate()
        self.process.join(5)
        self.tmp.cleanup()

    def test_control_process_serves_snapshot_without_content(self):
        self.assertEqual(self.client.send("hello")["type"], "capabilities")
        self.assertEqual(self.client.send("snapshot")["graph"]["nodes"], [])

    def test_missing_token_and_cross_origin_mutation_are_rejected(self):
        endpoint = json.loads(self.endpoint.read_text())
        for headers in [
            {},
            {"Authorization": "Bearer " + endpoint["token"], "Origin": "https://attacker.test"},
        ]:
            request = urllib.request.Request(endpoint["url"], data=b"{}", headers=headers)
            with (
                self.subTest(headers=list(headers)),
                self.assertRaises(urllib.error.HTTPError) as e,
            ):
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(e.exception.code, 403)

    def test_oversized_body_and_malformed_message_are_rejected(self):
        endpoint = json.loads(self.endpoint.read_text())
        for payload, status in [(b"x" * 262145, 413), (b"[]", 400), (b"{bad", 400)]:
            request = urllib.request.Request(
                endpoint["url"],
                data=payload,
                headers={"Authorization": "Bearer " + endpoint["token"]},
            )
            with self.subTest(status=status), self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(e.exception.code, status)
        self.assertEqual(self.client.send("snapshot")["graph"]["nodes"], [])

    def test_preexisting_endpoint_is_never_removed_or_overwritten(self):
        existing = Path(self.tmp.name) / "user-endpoint"
        existing.write_text("preserve me")
        with self.assertRaises(FileExistsError):
            serve(Path(self.tmp.name) / "second-journal", existing, 0)
        self.assertEqual(existing.read_text(), "preserve me")

    def test_endpoint_client_rejects_nonloopback_destinations(self):
        path = Path(self.tmp.name) / "remote-endpoint"
        path.write_text(json.dumps({"url": "https://example.test/command", "token": "private"}))
        with self.assertRaises(ValueError):
            Client(path)

    def test_idle_socket_cannot_block_authenticated_controls(self):
        endpoint = json.loads(self.endpoint.read_text())
        parsed = urlsplit(endpoint["url"])
        with socket.create_connection(("127.0.0.1", parsed.port), timeout=1):
            request = urllib.request.Request(
                endpoint["url"],
                data=b'{"protocol":"elyon-observer/0.1","type":"hello"}',
                headers={"Authorization": "Bearer " + endpoint["token"]},
            )
            with urllib.request.urlopen(request, timeout=1) as response:
                self.assertEqual(response.status, 200)

    def test_client_never_follows_redirects_with_broker_credentials(self):
        followed = []

        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", "/leak")
                self.end_headers()

            def do_GET(self):
                followed.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

        server = HTTPServer(("127.0.0.1", 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            path = Path(self.tmp.name) / "redirect-endpoint"
            path.write_text(
                json.dumps(
                    {"url": f"http://127.0.0.1:{server.server_port}/command", "token": "private"}
                )
            )
            with self.assertRaises(urllib.error.HTTPError) as error:
                Client(path).send("hello")
            self.assertEqual(error.exception.code, 302)
            self.assertEqual(followed, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == "__main__":
    unittest.main()
