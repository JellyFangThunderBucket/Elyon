"""Local visual workbench for recovered evidence and opt-in Chii debugging."""

import argparse
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .cli import Client

WEB = Path(__file__).parent / "web"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    runs = Path("artifacts/workbench")
    runs.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    process: subprocess.Popen[bytes] | None = None
    folders = sorted(runs.glob("run-*"))
    current: Path | None = folders[-1] if folders else None

    def state() -> dict[str, Any]:
        result: dict[str, Any] = {
            "running": process is not None and process.poll() is None,
            "snapshot": None,
            "report": None,
            "error": None,
        }
        if current is not None:
            result["run"] = current.name
            try:
                endpoint = current / "endpoint.json"
                if result["running"] and endpoint.exists():
                    result["snapshot"] = Client(endpoint).send("snapshot")
                elif (current / "snapshot.json").exists():
                    result["snapshot"] = json.loads((current / "snapshot.json").read_text())
                if (current / "report.json").exists():
                    result["report"] = json.loads((current / "report.json").read_text())
                if process is not None and process.poll() not in (None, 0):
                    result["error"] = (current / "run.log").read_text()[-4000:]
            except (OSError, ValueError):
                pass  # Broker may be starting or exiting; poll again.
        return result

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *values: Any) -> None:
            pass

        def reply(self, data: bytes, mime: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if mime in {"text/javascript", "text/css"}:
                self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.headers.get("Host") not in {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}:
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            if path == "/api/state":
                with lock:
                    self.reply(json.dumps(state()).encode(), "application/json")
            elif path == "/api/export":
                if current is None or not (current / "evidence.json").exists():
                    self.reply(b'{"error":"Run a capture first"}', "application/json", 409)
                else:
                    self.reply((current / "evidence.json").read_bytes(), "application/json")
            elif path in {
                "/",
                "/app.js",
                "/style.css",
                "/demo",
                "/themes.js",
                "/mobile-console.js",
                "/mobile-console.css",
                "/settings.js",
            }:
                name, mime = {
                    "/": ("index.html", "text/html"),
                    "/app.js": ("app.js", "text/javascript"),
                    "/style.css": ("style.css", "text/css"),
                    "/demo": ("demo.html", "text/html"),
                    "/themes.js": ("themes.js", "text/javascript"),
                    "/settings.js": ("settings.js", "text/javascript"),
                    "/mobile-console.js": ("mobile-console.js", "text/javascript"),
                    "/mobile-console.css": ("mobile-console.css", "text/css"),
                }[path]
                self.reply((WEB / name).read_bytes(), mime)
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            nonlocal process, current
            # A cross-origin page must not be able to launch local processes.
            if self.headers.get("Host") not in {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}:
                self.send_error(403)
                return
            origin = self.headers.get("Origin")
            if (
                self.path != "/api/run"
                or self.headers.get("Content-Type") != "application/json"
                or (origin is not None and origin != "http://" + self.headers.get("Host", ""))
            ):
                self.send_error(403)
                return
            with lock:
                if process is not None and process.poll() is None:
                    self.reply(b'{"error":"Capture already running"}', "application/json", 409)
                    return
                current = runs / f"run-{time.time_ns()}"
                current.mkdir(mode=0o700)
                with (current / "run.log").open("wb") as log:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "elyon.desktop",
                            "--output",
                            str(current),
                            "--runs",
                            "5",
                        ],
                        stdout=log,
                        stderr=log,
                    )
                self.reply(b'{"started":true}', "application/json", 202)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Elyon workbench: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
