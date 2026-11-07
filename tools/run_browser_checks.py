"""Run explicit browser checks with owned loopback-only workbench/Chii processes."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_ready(url: str, process: subprocess.Popen[bytes]) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with opener.open(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Local test service did not become ready: {url}")


def main() -> int:
    os.chdir(ROOT)
    output = ROOT / "artifacts/browser-checks"
    output.mkdir(parents=True, exist_ok=True)
    workbench_port, chii_port = free_port(), free_port()
    base = f"http://127.0.0.1:{workbench_port}"
    chii = f"http://127.0.0.1:{chii_port}"
    commands = [
        [sys.executable, "-m", "unittest", "validation.browser_check", "-v"],
        [sys.executable, "-m", "unittest", "validation.iphone_regression", "-v"],
        [sys.executable, "validation/workbench_check.py"],
        [sys.executable, "validation/mobile_console_check.py"],
    ]
    processes: list[subprocess.Popen[bytes]] = []
    results = []
    logs = []
    env = {**os.environ, "ELYON_TEST_BASE_URL": base, "ELYON_TEST_CHII_URL": chii}
    try:
        for name, command in [
            ("workbench", [sys.executable, "-m", "elyon.workbench", "--port", str(workbench_port)]),
            (
                "chii",
                [
                    str(ROOT / "node_modules/.bin/chii"),
                    "start",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(chii_port),
                ],
            ),
        ]:
            log = (output / f"{name}.log").open("wb")
            logs.append(log)
            processes.append(subprocess.Popen(command, stdout=log, stderr=log, env=env))
        wait_ready(base, processes[0])
        wait_ready(chii, processes[1])
        for index, command in enumerate(commands):
            started = time.monotonic()
            with (output / f"{index}.log").open("wb") as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
            row = {
                "command": " ".join(command),
                "exit": result.returncode,
                "seconds": round(time.monotonic() - started, 2),
                "log": f"{index}.log",
            }
            results.append(row)
            print(json.dumps(row), flush=True)
        (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        return int(any(row["exit"] for row in results))
    finally:
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
