"""Local deterministic HTTP fixtures. Content is deliberate test stimulus."""

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator


@contextmanager
def fixture_server() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            path = self.path.split('?')[0]
            status = 200
            headers = {'Content-Type': 'text/html', 'Cache-Control': 'no-store'}
            body = b'<!doctype html><title>Elyon fixture</title><p>Fixture</p>'
            if path == '/redirect':
                status, headers['Location'], body = 302, '/ok', b'redirect'
            elif path == '/ok':
                headers['Content-Type'], body = 'text/plain', b'elyon-response-v1'
            elif path in {'/cache', '/revalidate'}:
                headers.update(ETag='"elyon-v1"', **{'Cache-Control':
                               'max-age=3600' if path == '/cache' else 'no-cache'})
                if self.headers.get('If-None-Match') == '"elyon-v1"':
                    status, body = 304, b''
            elif path == '/sw.js':
                headers['Content-Type'] = 'application/javascript'
                body = (b"self.addEventListener('install',e=>self.skipWaiting());"
                        b"self.addEventListener('activate',e=>e.waitUntil(clients.claim()));"
                        b"self.addEventListener('fetch',e=>{if(e.request.url.endsWith('/sw-owned'))"
                        b"e.respondWith(new Response('owned',{status:203}));});")
            elif path == '/worker.js':
                headers['Content-Type'] = 'application/javascript'
                body = b"self.onmessage=()=>{fetch('/ok').then(()=>postMessage('done'))};"
            elif path == '/nested':
                body += b'<iframe src="/frame"></iframe>'
            elif path == '/frame':
                body += b'<script>new Worker("/worker.js").postMessage("run")</script>'
            elif path == '/policy':
                headers['Content-Security-Policy'] = "connect-src 'none'"
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
