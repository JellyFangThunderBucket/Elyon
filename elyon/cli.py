"""Authenticated loopback broker and portable command interface."""

import argparse
import hmac
import json
import os
import secrets
import signal
import socket
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import urlsplit

from .broker import Broker, import_archive
from .protocol import MAX_MESSAGE, PROTOCOL, ProtocolError, encode


class Client:
    def __init__(self, endpoint: Path):
        self.endpoint = json.loads(endpoint.read_text())
        address = urlsplit(self.endpoint["url"])
        if (
            address.scheme != "http"
            or address.hostname != "127.0.0.1"
            or address.username is not None
            or address.password is not None
            or address.port is None
            or address.path != "/command"
            or address.query
            or address.fragment
        ):
            raise ValueError("broker endpoint must be literal loopback HTTP /command")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
        ) -> None:
            return None

    def send(self, kind: str, **fields: Any) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint["url"],
            data=encode({"protocol": PROTOCOL, "type": kind, **fields}),
            headers={
                "Authorization": "Bearer " + self.endpoint["token"],
                "Content-Type": "application/json",
            },
        )
        # Local broker traffic must not traverse the outbound credential proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), self.NoRedirect())
        with opener.open(request, timeout=10) as response:
            value: dict[str, Any] = json.load(response)
            return value


class BoundedServer(ThreadingMixIn, HTTPServer):
    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler]):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)

    def get_request(self) -> tuple[socket.socket, Any]:
        request, address = super().get_request()
        request.settimeout(2)
        return request, address

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def serve(journal: Path, endpoint: Path, port: int = 0) -> None:
    broker = Broker(journal)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # Do not log authorization or inspected content.

        def do_POST(self) -> None:
            self.connection.settimeout(2)
            if (
                self.path != "/command"
                or self.headers.get("Origin") is not None
                or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)
            ):
                self.send_error(403)
                return
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 < size <= MAX_MESSAGE:
                    self.send_error(413)
                    return
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ProtocolError("truncated request")
                message = json.loads(raw)
                result = broker.dispatch(message)
                data = encode(result)
            except (ValueError, TypeError, KeyError, BufferError, RecursionError) as error:
                data = encode({"error": type(error).__name__, "reason": str(error)[:512]})
                self.send_response(400)
            except OSError:
                data = encode({"error": "storage-failure", "reason": "journal requires recovery"})
                self.send_response(503)
            else:
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    server = BoundedServer(("127.0.0.1", port), Handler)
    endpoint_inode: int | None = None
    try:
        endpoint.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=endpoint.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(
                encode({"url": f"http://127.0.0.1:{server.server_port}/command", "token": token})
            )
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, endpoint)
            endpoint_inode = endpoint.stat().st_ino
        finally:
            temporary.unlink()
        # SIGTERM follows the same cleanup path as an interactive Ctrl-C.
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        broker.close()
        if endpoint_inode is not None and endpoint.exists():
            if endpoint.stat().st_ino == endpoint_inode:
                endpoint.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    host = subs.add_parser("serve")
    host.add_argument("--journal", type=Path, required=True)
    host.add_argument("--endpoint", type=Path, required=True)
    host.add_argument("--port", type=int, default=0)
    command = subs.add_parser("command", help="send one elyon-observer/0.1 JSON command")
    command.add_argument("--endpoint", type=Path, required=True)
    command.add_argument("message", help="JSON with type and command fields")
    restore = subs.add_parser("import")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "serve":
        serve(args.journal, args.endpoint, args.port)
    elif args.action == "command":
        message = json.loads(args.message)
        kind = message.pop("type")
        print(json.dumps(Client(args.endpoint).send(kind, **message), indent=2))
    elif args.action == "import":
        broker = import_archive(args.journal, json.loads(args.archive.read_text()))
        try:
            print(json.dumps(broker.snapshot(), indent=2))
        finally:
            broker.close()


if __name__ == "__main__":
    main()
