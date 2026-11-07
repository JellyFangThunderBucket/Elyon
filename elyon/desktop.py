"""Real Chromium validation host, explicitly NOT a Gecko or iPhone implementation."""

import argparse
import asyncio
import json
import math
import multiprocessing
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Request, Response, async_playwright

from .cli import Client, serve
from .fixtures import fixture_server
from .protocol import event

SOURCE = "desktop-chromium-playwright"
CAPABILITIES = {
    name: {
        "supported": supported,
        "permitted": supported,
        "enabled": supported,
        "healthy": supported,
    }
    for name, supported in [
        ("requests", True),
        ("responseMetadata", True),
        ("redirectIdentity", True),
        ("nativeGecko", False),
        ("pageVisibleResponse", False),
        ("nativeCausalIdentity", False),
    ]
}


class DesktopAdapter:
    """Metadata only. No Fetch/XHR patches or response modification.

    The request/response observations are Playwright's browser protocol view, not
    native channel probes or proof of what Fetch/XHR exposed to page JavaScript.
    """

    def __init__(self, client: Client, context: BrowserContext):
        self.client, self.context = client, context
        self.attachment = client.send(
            "attach", scope={"kind": "browser-context"}, source=SOURCE, capabilities=CAPABILITIES
        )["attachment"]
        self.capture: str | None = None
        self.sequence = 0
        self.generation = 1
        self.requests: OrderedDict[Request, tuple[str, dict[str, str] | None]] = OrderedDict()
        self.active = True
        self.errors: list[str] = []
        context.on("request", self.on_request)
        context.on("response", self.on_response)
        context.on("requestfailed", self.on_failed)
        self.upsert()

    @property
    def target(self) -> dict[str, str]:
        return {"id": "document", "generation": str(self.generation)}

    def upsert(self) -> None:
        self.client.send(
            "target.upsert",
            attachment=self.attachment,
            target=self.target,
            parent=None,
            targetKind="document",
        )

    def start(self, capture: str) -> None:
        self.capture = capture
        self.client.send(
            "start",
            attachment=self.attachment,
            capture=capture,
            revision="1",
            plan={"mode": "metadata", "adapter": SOURCE},
            target=self.target,
        )
        # Listener installation is already complete. This acknowledgment is separate from start.
        self.client.send(
            "activation",
            attachment=self.attachment,
            capture=capture,
            revision="1",
            target=self.target,
        )

    def emit(
        self,
        kind: str,
        evidence: dict[str, Any],
        *,
        point: str = "playwright-context-network",
        certainty: str = "observed",
        identity: dict[str, str] | None = None,
    ) -> str:
        if not self.capture:
            raise RuntimeError("adapter not capturing")
        self.sequence += 1
        value = event(
            self.attachment,
            self.capture,
            "playwright",
            "host-1",
            self.sequence,
            kind,
            evidence,
            target=identity,
            certainty=certainty,
            point=point,
            source=SOURCE,
        )
        result = self.client.send("events", attachment=self.attachment, batch=[value])
        if result.get("ack") != [value["id"]]:
            raise BufferError("broker did not acknowledge delivered evidence")
        return str(value["id"])

    def request_target(self, request: Request) -> dict[str, str] | None:
        # This host only assigns identity for the coordinated main document.
        # Worker/frame/navigation requests remain unknown, never mislabeled as it.
        try:
            if (
                request.frame == self.context.pages[0].main_frame
                and not request.is_navigation_request()
            ):
                return self.target
        except Exception:
            pass  # Service-worker requests may have no Frame at all.
        return None

    def on_request(self, request: Request) -> None:
        if not self.active or not self.capture:
            return
        try:
            # This narrow adapter observes one document; other contexts remain unknown.
            identity = self.emit(
                "RequestAttempt",
                {"method": request.method, "url": request.url, "initiator": None},
                identity=self.request_target(request),
            )
            previous = request.redirected_from
            if previous is not None:
                prior = self.requests.get(previous)
                if prior:
                    source = prior[0]
                    redirect = self.emit(
                        "Redirect",
                        {
                            "fromRequest": source,
                            "toRequest": identity,
                            "basis": "Playwright.Request.redirected_from",
                        },
                    )
                    self.emit(
                        "Relationship",
                        {
                            "from": source,
                            "to": identity,
                            "relation": "redirect-to",
                            "support": [redirect],
                        },
                        certainty="derived",
                    )
                else:
                    self.client.send(
                        "gap",
                        attachment=self.attachment,
                        reason="redirect-identity-not-retained",
                        missing=None,
                    )
            self.requests[request] = (identity, self.request_target(request))
            if len(self.requests) > 256:
                self.requests.popitem(last=False)
                self.client.send(
                    "gap", attachment=self.attachment, reason="adapter-object-limit", missing=None
                )
        except Exception as error:
            self._failure(error)

    def on_response(self, response: Response) -> None:
        if not self.active or not self.capture:
            return
        try:
            retained = self.requests.get(response.request)
            original_target = retained[1] if retained else None
            response_target = original_target if original_target == self.target else None
            identity = self.emit(
                "ResponseVersion",
                {
                    "url": response.url,
                    "status": response.status,
                    "statusObservation": "Playwright.Response.status; raw wire status unavailable",
                    "fromServiceWorker": response.from_service_worker,
                    "requestObservedTarget": original_target,
                    "sourceClassification": {
                        "certainty": "unavailable",
                        "reason": "origin-unobserved",
                    },
                    "pageExposure": {"certainty": "unavailable", "reason": "not-instrumented"},
                },
                identity=response_target,
            )
            request_id = retained[0] if retained else None
            if request_id:
                self.emit(
                    "Relationship",
                    {
                        "from": request_id,
                        "to": identity,
                        "relation": "response-for",
                        "support": [identity],
                    },
                    certainty="derived",
                )
        except Exception as error:
            self._failure(error)

    def on_failed(self, request: Request) -> None:
        if self.active and self.capture:
            try:
                retained = self.requests.get(request)
                self.emit(
                    "Termination",
                    {
                        "request": retained[0] if retained else None,
                        "failure": request.failure,
                        "policyDecision": None,
                    },
                )
            except Exception as error:
                self._failure(error)

    def _failure(self, error: Exception) -> None:
        # Bound diagnostic memory; the host fails verification if ANY callback failed.
        self.active = False
        self.errors.append(type(error).__name__)
        self.errors = self.errors[-16:]
        try:
            self.client.send(
                "health",
                attachment=self.attachment,
                healthy=False,
                reason="adapter-ingestion-failure",
            )
        except Exception:
            pass  # Transport may be gone. Host detects and marks incomplete on reconnect.

    def stop(self, *, already_requested: bool = False) -> None:
        if not already_requested:
            self.client.send("stop", attachment=self.attachment, capture=self.capture)
        self.client.send("stopped", attachment=self.attachment, capture=self.capture)
        self.capture = None

    def close(self) -> None:
        self.active = False
        self.context.remove_listener("request", self.on_request)
        self.context.remove_listener("response", self.on_response)
        self.context.remove_listener("requestfailed", self.on_failed)
        self.requests.clear()
        self.client.send("detach", attachment=self.attachment)


async def run_validation(output: Path, runs: int = 100) -> dict[str, Any]:
    if not 1 <= runs <= 200:
        raise ValueError("runs must be 1..200")
    output.mkdir(parents=True, exist_ok=True)
    endpoint = output / "endpoint.json"
    if (output / "journal.ndjson").exists():
        raise FileExistsError("use a fresh output directory to preserve previous evidence")
    broker_process = multiprocessing.get_context("spawn").Process(
        target=serve, args=(output / "journal.ndjson", endpoint, 0)
    )
    broker_process.start()
    deadline = time.monotonic() + 10
    while not endpoint.exists() and broker_process.is_alive() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    client = Client(endpoint)
    try:
        with fixture_server() as origin:
            async with async_playwright() as playwright:
                # Keep Chromium's sandbox ON. Run the host outside a nested command
                # sandbox if required; never substitute --no-sandbox.
                browser = await playwright.chromium.launch(
                    executable_path="/usr/bin/chromium", headless=True, chromium_sandbox=True
                )
                try:
                    version = browser.version
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.goto(origin)
                    adapter = DesktopAdapter(client, context)
                    for run in range(runs):
                        capture = f"redirect-{run}"
                        adapter.start(capture)
                        result = await page.evaluate(
                            "async () => {const r=await fetch('/redirect');"
                            "return [r.status,await r.text()]}"
                        )
                        if result != [200, "elyon-response-v1"]:
                            raise AssertionError(f"unexpected fixture result: {result}")
                        adapter.stop()
                        snapshot = client.send("snapshot")
                        nodes = [e for e in snapshot["graph"]["nodes"] if e["capture"] == capture]
                        edges = [
                            e for e in snapshot["graph"]["relationships"] if e["capture"] == capture
                        ]
                        if sorted(
                            e["evidence"]["status"] for e in nodes if e["kind"] == "ResponseVersion"
                        ) != [200, 302]:
                            raise AssertionError("missing redirect or final response evidence")
                        if sum(e["evidence"]["relation"] == "redirect-to" for e in edges) != 1:
                            raise AssertionError("missing verified redirect identity")
                    adapter.start("stall")
                    # Prove navigation invalidates activation, then explicitly reactivate.
                    adapter.generation += 1
                    adapter.upsert()
                    if client.send("snapshot")["ready"]:
                        raise AssertionError("navigation did not invalidate readiness")
                    client.send(
                        "activation",
                        attachment=adapter.attachment,
                        capture="stall",
                        revision="1",
                        target=adapter.target,
                    )
                    # All actual navigation in this fixture is coordinated by the host.
                    await page.goto(origin + "/ok")
                    async with page.expect_console_message(
                        predicate=lambda msg: msg.text == "elyon-stall-start"
                    ):
                        stall = asyncio.create_task(
                            page.evaluate(
                                "() => {console.log('elyon-stall-start');const t=performance.now();"
                                "while(performance.now()-t<5000){};"
                                "return (performance.now()-t)/1000}"
                            )
                        )
                    latencies: list[float] = []
                    for _ in range(10):
                        started = time.monotonic()
                        snap = await asyncio.to_thread(client.send, "snapshot")
                        latencies.append((time.monotonic() - started) * 1000)
                        if stall.done() or not snap["graph"]["nodes"]:
                            raise AssertionError("content was not stalled during broker control")
                        await asyncio.sleep(0.05)
                    stopped = await asyncio.to_thread(
                        client.send, "stop", attachment=adapter.attachment, capture="stall"
                    )
                    if stopped["state"] != "stop-requested" or stall.done():
                        raise AssertionError("stop waited for content")
                    # Export is a preserved immutable snapshot during the stall as well.
                    archive = await asyncio.to_thread(client.send, "export", redacted=True)
                    (output / "during-stall.json").write_bytes(
                        json.dumps(archive, sort_keys=True).encode()
                    )
                    stall_seconds = await stall
                    before = {e["id"] for e in client.send("snapshot")["graph"]["nodes"]}
                    # Actual renderer crash using the documented Chromium Page.crash command.
                    cdp = await context.new_cdp_session(page)
                    async with page.expect_event("crash", timeout=10000):
                        crash = asyncio.create_task(cdp.send("Page.crash"))
                    crash.cancel()
                    await asyncio.gather(crash, return_exceptions=True)
                    adapter.emit(
                        "Termination", {"reason": "page-crash-event"}, point="playwright-page-crash"
                    )
                    client.send(
                        "target.end",
                        attachment=adapter.attachment,
                        target=adapter.target,
                        reason="process-terminated",
                    )
                    adapter.stop(already_requested=True)
                    after = client.send("snapshot")
                    preserved = before.issubset({e["id"] for e in after["graph"]["nodes"]})
                    if not preserved or adapter.errors:
                        raise AssertionError(f"evidence loss or callback failure: {adapter.errors}")
                    adapter.close()
                    archive = client.send("export", redacted=True)
                    (output / "evidence.json").write_text(json.dumps(archive, indent=2))
                    (output / "snapshot.json").write_text(
                        json.dumps(client.send("snapshot"), indent=2)
                    )
                    report = {
                        "source": SOURCE,
                        "browserVersion": version,
                        "verifiedRedirectRuns": runs,
                        "stallSeconds": stall_seconds,
                        "controlsDuringStall": len(latencies) + 2,
                        "brokerControlLatencyMs": {
                            "samples": latencies,
                            "p95": sorted(latencies)[math.ceil(len(latencies) * 0.95) - 1],
                        },
                        "deliveredEvidencePreservedAfterCrash": preserved,
                        "retainedAdapterObjects": len(adapter.requests),
                        "nativeUIVerified": False,
                        "nativePerformanceTargetsMeasured": False,
                        "journalBytes": after["journalBytes"],
                    }
                    (output / "report.json").write_text(json.dumps(report, indent=2))
                    return report
                finally:
                    await browser.close()
    finally:
        broker_process.terminate()
        broker_process.join(5)
        if broker_process.is_alive():
            broker_process.kill()
            broker_process.join(5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()
    workload = (
        run_fixture_validation(args.output)
        if args.fixtures
        else run_validation(args.output, args.runs)
    )
    print(json.dumps(asyncio.run(workload), indent=2))


async def run_fixture_validation(output: Path) -> dict[str, Any]:
    """Exercise broader fixtures without upgrading unsupported native claims."""
    output.mkdir(parents=True, exist_ok=True)
    endpoint = output / "endpoint.json"
    process = multiprocessing.get_context("spawn").Process(
        target=serve, args=(output / "journal.ndjson", endpoint, 0)
    )
    process.start()
    try:
        deadline = time.monotonic() + 10
        while not endpoint.exists() and process.is_alive() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        client = Client(endpoint)
        with fixture_server() as origin:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    executable_path="/usr/bin/chromium", headless=True, chromium_sandbox=True
                )
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.goto(origin)
                    adapter = DesktopAdapter(client, context)
                    adapter.start("coverage-fixtures")
                    statuses = await page.evaluate("""async () => {
                        const statuses=[];
                        for(const url of ['/cache','/cache','/revalidate','/revalidate']) {
                            const response=await fetch(url);await response.text();
                            statuses.push(response.status);
                        }
                        return statuses;
                    }""")
                    if statuses != [200, 200, 200, 200]:
                        raise AssertionError("cache/revalidation fixture failed")
                    owned = await page.evaluate("""async () => {
                        await navigator.serviceWorker.register('/sw.js');
                        await navigator.serviceWorker.ready;
                        if(!navigator.serviceWorker.controller) await new Promise(resolve=>
                            navigator.serviceWorker.addEventListener('controllerchange',resolve,
                                {once:true}));
                        const r=await fetch('/sw-owned');return [r.status,await r.text()];
                    }""")
                    if owned != [203, "owned"]:
                        raise AssertionError("service worker fixture failed")
                    # Test content creates frames/workers; it is not injected instrumentation.
                    await page.evaluate("""() => {const f=document.createElement('iframe');
                        f.src='/nested';document.body.append(f)}""")
                    # Read durable fixture completion state rather than depending on
                    # delivery of a transient console notification from a nested frame.
                    await (
                        page.frame_locator('iframe[src="/nested"]')
                        .frame_locator('iframe[src="/frame"]')
                        .locator('body[data-worker-done="true"]')
                        .wait_for(timeout=10000)
                    )
                    await page.evaluate("""() => {const f=document.createElement('iframe');
                        f.id='policy';f.src='/policy';document.body.append(f)}""")
                    await page.locator("#policy").wait_for()
                    policy_frame = page.frame_locator("#policy")
                    await policy_frame.locator("p").wait_for()
                    iframe = page.frame(url=origin + "/policy")
                    if iframe is None:
                        raise AssertionError("policy frame did not load")
                    blocked = await iframe.evaluate("""async () => {
                        try {await fetch('/ok');return false} catch {return true}
                    }""")
                    if not blocked:
                        raise AssertionError("CSP fixture failed to block fetch")
                    async with page.expect_request(lambda request: request.url.endswith("/slow")):
                        await page.evaluate("""() => {
                            window.elyonPending=fetch('/slow').then(r=>r.text())
                        }""")
                    adapter.generation += 1
                    adapter.upsert()
                    client.send(
                        "activation",
                        attachment=adapter.attachment,
                        capture="coverage-fixtures",
                        revision="1",
                        target=adapter.target,
                    )
                    await page.evaluate("() => window.elyonPending")
                    failed = await page.evaluate("""async () => {
                        try {await fetch('/disconnect');return false} catch {return true}
                    }""")
                    adapter.stop()
                    snapshot = client.send("snapshot")
                    nodes = snapshot["graph"]["nodes"]
                    failure_refs = [
                        n["evidence"].get("request") for n in nodes if n["kind"] == "Termination"
                    ]
                    failure_ids_valid = bool(failed and failure_refs) and all(
                        value is None or isinstance(value, str) for value in failure_refs
                    )
                    late_responses = [
                        n
                        for n in nodes
                        if n["kind"] == "ResponseVersion"
                        and n["evidence"].get("url", "").endswith("/slow")
                    ]
                    late_identity_valid = bool(late_responses) and all(
                        n["target"] is None or n["target"]["generation"] == "1"
                        for n in late_responses
                    )
                    sw = any(
                        n["kind"] == "ResponseVersion"
                        and n["evidence"].get("fromServiceWorker") is True
                        for n in nodes
                    )
                    unknown_child = any(
                        n["target"] is None and "/worker.js" in n["evidence"].get("url", "")
                        for n in nodes
                    )
                    if not sw or not unknown_child or adapter.errors:
                        raise AssertionError("missing SW/unknown target observation")
                    adapter.close()
                    result = {
                        "source": SOURCE,
                        "cacheAndRevalidationStimuliCompleted": True,
                        "serviceWorkerHandlingObserved": sw,
                        "policyFixtureBlockedFetch": bool(blocked),
                        "nestedWorkerFixtureCompleted": True,
                        "unknownChildTargetsPreserved": True,
                        "wire304OrCacheOriginVerified": False,
                        "lateResponseDidNotAcquireNewGeneration": late_identity_valid,
                        "failedRequestReferencesValid": failure_ids_valid,
                    }
                    (output / "report.json").write_text(json.dumps(result, indent=2))
                    (output / "evidence.json").write_text(
                        json.dumps(client.send("export", redacted=True), indent=2)
                    )
                    return result
                finally:
                    await browser.close()
    finally:
        process.terminate()
        process.join(5)


if __name__ == "__main__":
    main()
