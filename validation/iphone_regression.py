"""Real-browser regressions for the standalone page console; no native-iOS claim."""

import hashlib
import json
import os
import subprocess
import threading
import time
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


class Fixtures(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/fixture/delay":
            time.sleep(float(parse_qs(urlsplit(self.path).query).get("ms", ["100"])[0]) / 1000)
            self.reply(200, b'{"fixture":"delayed"}')
        elif path == "/fixture/fail":
            self.reply(503, b'{"fixture":"http-error"}')
        elif path == "/fixture/disconnect":
            self.close_connection = True
            self.connection.close()
        elif path == "/fixture/redirect":
            self.send_response(302)
            self.send_header("Location", "/fixtures/response.json")
            self.end_headers()
        elif path == "/denied-eval.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header(
                "Content-Security-Policy", "script-src 'self'; style-src 'self' 'unsafe-inline'"
            )
            self.end_headers()
            self.wfile.write((ROOT / "dist/iphone-demo/index.html").read_bytes())
        else:
            super().do_GET()

    def reply(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Explicit abort/teardown fixtures disconnect before the reply.


class IPhoneConsoleRegression(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["node", "tools/build-demo.mjs"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL
        )
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(Fixtures, directory=str(ROOT / "dist/iphone-demo"))
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        executable = os.getenv("ELYON_CHROMIUM_EXECUTABLE", "/usr/bin/chromium")
        self.browser = await self.playwright.chromium.launch(
            executable_path=None if executable == "bundled" else executable, chromium_sandbox=True
        )
        self.page = await self.browser.new_page(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        await self.page.goto(self.url)
        await self.page.locator("#elyon-console .console").wait_for()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def rows(self):
        return await self.page.evaluate("elyonConsole.snapshot({redacted:false}).requests")

    async def reinstall(self, preparation=""):
        await self.page.evaluate("elyonConsole.destroy()")
        if preparation:
            await self.page.evaluate(preparation)
        await self.page.evaluate('import("/mobile-console.js").then(m=>m.createConsole().open())')

    async def test_fetch_values_body_identity_abort_and_rejection(self):
        result = await self.page.evaluate("""async () => {
          const data=await fetch('/fixtures/response.json');
          const unused=!data.bodyUsed;const body=await data.json();
          const failed=await fetch('/fixture/fail');
          const controller=new AbortController();controller.abort();let name;
          try{await fetch('/fixture/delay',{signal:controller.signal})}catch(e){name=e.name}
          let rejected=false;try{await fetch('/fixture/disconnect')}catch{rejected=true}
          return {unused,body,failed:failed.status,name,rejected};
        }""")
        self.assertTrue(result["unused"])
        self.assertEqual(result["body"]["fixture"], "elyon-device-lab")
        self.assertEqual(result["failed"], 503)
        self.assertEqual(result["name"], "AbortError")
        self.assertTrue(result["rejected"])
        rows = await self.rows()
        self.assertEqual(
            [r["outcome"] for r in rows], ["fulfilled", "fulfilled", "rejected", "rejected"]
        )
        self.assertEqual([r["status"] for r in rows], [200, 503, None, None])
        self.assertTrue(all(r["source"] == "page-instrumentation" for r in rows))
        self.assertFalse(self.errors)

    async def test_fetch_does_not_repeat_url_coercion_or_init_getters(self):
        result = await self.page.evaluate("""async () => {
          let urls=0,methods=0;
          const url={toString(){urls++;return '/fixtures/response.json'}};
          const init={get method(){methods++;return 'GET'}};
          const r=await fetch(url,init);return {urls,methods,status:r.status};
        }""")
        self.assertEqual(result, {"urls": 1, "methods": 1, "status": 200})
        row = (await self.rows())[0]
        self.assertIsNone(row["method"])
        self.assertIsNone(row["url"])
        self.assertTrue(row["responseURL"].endswith("/fixtures/response.json"))

    async def test_fetch_preserves_response_and_error_objects_and_sync_throw(self):
        await self.reinstall("""() => {
          window.fixtureResponse=new Response('untouched');window.fixtureError=new Error('same');
          window.fixtureNativeFetch=window.fetch;
          window.fixtureBroken=Object.defineProperty({},"status",{get(){throw Error("denied")}});
          window.fetch=function(mode){if(mode==='throw')throw fixtureError;
            if(mode==='broken')return Promise.resolve(fixtureBroken);
            return mode==='reject'?Promise.reject(fixtureError):Promise.resolve(fixtureResponse)};
        }""")
        result = await self.page.evaluate("""async () => {
          const response=await fetch('ok');let sameError=false,sync=false;
          try{await fetch('reject')}catch(e){sameError=e===fixtureError}
          try{fetch('throw')}catch(e){sync=e===fixtureError}
          const broken=await fetch('broken');
          return {same:response===fixtureResponse,unused:!response.bodyUsed,
            sameError,sync,sameBroken:broken===fixtureBroken};
        }""")
        self.assertTrue(all(result.values()))
        self.assertEqual(
            [r["outcome"] for r in await self.rows()],
            ["fulfilled", "rejected", "call-threw", "unavailable"],
        )

    async def xhr_case(self, event):
        return await self.page.evaluate(
            """
            (event) =>
              new Promise((resolve) => {
                const x = new XMLHttpRequest(),
                  statuses = [],
                  events = [];
                let first = true;
                x.addEventListener("readystatechange", () => events.push(x.readyState));
                const next = () => {
                  if (first) {
                    first = false;
                    statuses.push(x.status);
                    x.open("GET", "/fixture/fail");
                    x.send();
                  }
                };
                if (event === "readystatechange")
                  x.onreadystatechange = () => {
                    if (x.readyState === 4) next();
                  };
                else x[event] = next;
                x.addEventListener("loadend", () => {
                  if (!first && x.readyState === 4 && x.status === 503)
                    resolve({ statuses, final: x.status, events });
                });
                x.open("GET", "/fixtures/response.json");
                x.send();
              })
            """,
            event,
        )

    async def test_xhr_reuse_in_load_preserves_each_status(self):
        result = await self.xhr_case("onload")
        self.assertEqual(result["statuses"], [200])
        self.assertEqual(result["final"], 503)
        rows = await self.rows()
        self.assertEqual([r["status"] for r in rows], [200, 503])
        self.assertEqual(len({r["id"] for r in rows}), 2)
        self.assertEqual(rows[0]["gap"], "reopened-before-loadend")
        self.assertEqual(rows[1]["events"][-1]["phase"], "loadend")
        self.assertEqual([e["phase"] for e in rows[1]["events"]].count("load"), 1)

    async def test_xhr_reuse_in_done_reports_gap_without_inventing_status(self):
        await self.xhr_case("readystatechange")
        rows = await self.rows()
        self.assertEqual(rows[0]["gap"], "reopened-before-loadend")
        # Preexisting listeners may reopen before our DONE listener. Retain the
        # last actual observation (possibly headers), never the new request's 0.
        self.assertIn(rows[0]["status"], [None, 200])
        self.assertEqual(rows[1]["status"], 503)

    async def test_xhr_reuse_in_loadend(self):
        await self.xhr_case("onloadend")
        self.assertEqual([row["status"] for row in await self.rows()], [200, 503])

    async def test_disabled_fetch_passes_through_and_opaque_response_is_not_failure(self):
        await self.reinstall("""() => {
            window.savedNativeFetch=fetch;
            window.fixturePromise=Promise.resolve(new Response('same'));
            window.fetch=()=>fixturePromise;
        }""")
        root = self.page.locator("#elyon-console")
        await self.page.evaluate('elyonConsole.showTab("settings")')
        await root.locator("#setting-network").uncheck()
        self.assertTrue(await self.page.evaluate('fetch("x")===fixturePromise'))
        self.assertEqual(await self.rows(), [])
        await self.reinstall("() => {window.fetch=window.savedNativeFetch;}")
        await self.page.evaluate('elyonConsole.showTab("settings")')
        await root.locator("#setting-network").check()
        other = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(Fixtures, directory=str(ROOT / "dist/iphone-demo"))
        )
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        try:
            result = await self.page.evaluate(
                """async url => {
                const response=await fetch(url,{mode:'no-cors'});
                return {status:response.status,type:response.type};
            }""",
                f"http://127.0.0.1:{other.server_port}/fixtures/response.json",
            )
            self.assertEqual(result, {"status": 0, "type": "opaque"})
            self.assertEqual((await self.rows())[0]["outcome"], "fulfilled")
        finally:
            other.shutdown()
            other.server_close()
            thread.join()

    async def test_dom_picker_can_be_cancelled_or_used_without_lingering_interception(self):
        root = self.page.locator("#elyon-console")
        await self.page.evaluate('elyonConsole.showTab("elements")')
        await root.locator("#pick").click()
        await self.page.keyboard.press("Escape")
        self.assertTrue(await root.locator(".console").is_visible())
        await root.locator("#pick").click()
        await self.page.locator("#counter").click()
        self.assertEqual(await self.page.locator("#counter").inner_text(), "Count: 0")
        meta = json.loads(await root.locator("#element-metadata").inner_text())
        self.assertEqual(meta["id"], "counter")
        await self.page.evaluate("elyonConsole.destroy()")
        await self.page.locator("#counter").click()
        self.assertEqual(await self.page.locator("#counter").inner_text(), "Count: 1")

    async def test_xhr_native_event_sequence_unchanged(self):
        script = """
            () =>
              new Promise((resolve) => {
                const x = new XMLHttpRequest(),
                  events = [];
                for (const type of [
                  "readystatechange",
                  "loadstart",
                  "progress",
                  "load",
                  "error",
                  "abort",
                  "timeout",
                  "loadend",
                ])
                  x.addEventListener(type, () => {
                    events.push([type, x.readyState, x.status]);
                    if (type === "loadend") resolve(events);
                  });
                x.open("GET", "/fixtures/response.json");
                x.send();
              })
            """
        with_console = await self.page.evaluate(script)
        row = (await self.rows())[0]
        phases = [e["phase"] for e in row["events"]]
        self.assertLess(phases.index("done"), phases.index("load"))
        self.assertLess(phases.index("load"), phases.index("loadend"))
        await self.page.evaluate("elyonConsole.destroy()")
        native = await self.page.evaluate(script)
        self.assertEqual(with_console, native)

    async def test_xhr_abort_timeout_network_failure_and_http_failure(self):
        result = await self.page.evaluate("""
            async () => {
              const run = (url, mode) =>
                new Promise((resolve) => {
                  const x = new XMLHttpRequest();
                  x.onloadend = () => resolve({ status: x.status });
                  x.open("GET", url);
                  if (mode === "timeout") x.timeout = 10;
                  x.send();
                  if (mode === "abort") x.abort();
                });
              return [
                await run("/fixture/delay?ms=100", "abort"),
                await run("/fixture/delay?ms=100", "timeout"),
                await run("/fixture/disconnect"),
                await run("/fixture/fail"),
              ];
            }
            """)
        self.assertEqual([x["status"] for x in result], [0, 0, 0, 503])
        self.assertEqual(
            [r["outcome"] for r in await self.rows()], ["abort", "timeout", "error", "load"]
        )

    async def test_xhr_invalid_calls_do_not_corrupt_active_request(self):
        result = await self.page.evaluate("""() => new Promise(resolve=>{
          const x=new XMLHttpRequest();let doubleSend,invalidOpen;
          x.onloadend=()=>resolve({doubleSend,invalidOpen,status:x.status});
          x.open('GET','/fixture/delay');x.send();try{x.send()}catch(e){doubleSend=e.name}
          try{x.open('INVALID METHOD','/fixture/fail')}catch(e){invalidOpen=e.name}
        })""")
        self.assertEqual(result["doubleSend"], "InvalidStateError")
        self.assertEqual(result["invalidOpen"], "SyntaxError")
        rows = await self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], 200)

    async def test_xhr_listener_denial_does_not_break_native_send(self):
        result = await self.page.evaluate("""() => new Promise(resolve => {
            const x=new XMLHttpRequest();
            x.onloadend=()=>resolve(x.status);
            x.addEventListener=()=>{throw new Error('subscription denied')};
            x.open('GET','/fixtures/response.json');x.send();
        })""")
        self.assertEqual(result, 200)
        row = (await self.rows())[0]
        self.assertEqual(row["outcome"], "unavailable")
        self.assertEqual(row["gap"], "event-listener-access-denied")
        self.assertFalse(self.errors)

    async def test_xhr_synchronous_and_nested_reuse(self):
        result = await self.page.evaluate("""
            () => {
              const x = new XMLHttpRequest();
              let first = true;
              const statuses = [];
              x.onload = () => {
                statuses.push(x.status);
                if (first) {
                  first = false;
                  x.open("GET", "/fixture/fail", false);
                  x.send();
                }
              };
              x.open("GET", "/fixtures/response.json", false);
              x.send();
              return statuses;
            }
            """)
        self.assertEqual(result, [200, 503])
        rows = await self.rows()
        self.assertEqual([r["status"] for r in rows], [200, 503])
        self.assertTrue(all(r["outcome"] != "pending" for r in rows))

    async def test_repeated_install_teardown_pending_listeners_and_later_wrappers(self):
        result = await self.page.evaluate("""
            async () => {
              const module = await import("/mobile-console.js");
              elyonConsole.destroy();
              const originals = {
                fetch,
                log: console.log,
                open: XMLHttpRequest.prototype.open,
                send: XMLHttpRequest.prototype.send,
              };
              let added = 0,
                removed = 0;
              const add = XMLHttpRequest.prototype.addEventListener,
                remove = XMLHttpRequest.prototype.removeEventListener;
              XMLHttpRequest.prototype.addEventListener = function (...a) {
                added++;
                return add.apply(this, a);
              };
              XMLHttpRequest.prototype.removeEventListener = function (...a) {
                removed++;
                return remove.apply(this, a);
              };
              for (let i = 0; i < 15; i++) {
                const c = module.createConsole();
                if (module.createConsole() !== c) throw Error("duplicate");
                const x = new XMLHttpRequest();
                x.open("GET", "/fixture/delay");
                x.send();
                c.destroy();
                c.destroy();
                x.abort();
              }
              const restored =
                fetch === originals.fetch &&
                console.log === originals.log &&
                XMLHttpRequest.prototype.open === originals.open &&
                XMLHttpRequest.prototype.send === originals.send;
              const c = module.createConsole();
              const wrapped = fetch;
              const later = (...a) => wrapped(...a);
              window.fetch = later;
              c.destroy();
              const kept = fetch === later;
              window.fetch = originals.fetch;
              module.createConsole();
              console.log("one-copy");
              return {
                added,
                removed,
                restored,
                kept,
                hosts: document.querySelectorAll("#elyon-console").length,
                copies: elyonConsole
                  .snapshot({ redacted: false })
                  .logs.filter((l) => l.text === "one-copy").length,
              };
            }
            """)
        self.assertEqual(result["added"], result["removed"])
        self.assertTrue(result["restored"] and result["kept"])
        self.assertEqual(result["hosts"], 1)
        self.assertEqual(result["copies"], 1)

    async def test_protected_and_missing_apis_are_reported(self):
        await self.reinstall("""
            () => {
              Object.defineProperty(window, "fetch", {
                value: fetch,
                writable: false,
                configurable: true,
              });
              Object.defineProperty(console, "warn", {
                value: console.warn,
                writable: false,
                configurable: true,
              });
              window.XMLHttpRequest = undefined;
            }
            """)
        caps = await self.page.evaluate("elyonConsole.snapshot().capabilities")
        self.assertEqual(caps["fetch"]["status"], "denied")
        self.assertEqual(caps["xhr"]["status"], "unsupported")
        self.assertEqual(caps["console.warn"]["status"], "denied")
        self.assertFalse(self.errors)

    async def test_evaluation_async_errors_previews_and_no_double_execution(self):
        root = self.page.locator("#elyon-console")

        async def run(source, mode="script"):
            await root.locator("#eval-mode").select_option(mode)
            await root.locator("#expression").fill(source)
            await root.locator("#repl button").click()

        await run("await Promise.resolve(42)", "await")
        await root.locator(".level-result").filter(has_text="42").wait_for()
        await run('throw new Error("clear-evaluation-error")')
        await root.locator(".level-error").filter(has_text="clear-evaluation-error").wait_for()
        await run('window.once=(window.once||0)+1; throw new Error("once")')
        self.assertEqual(await self.page.evaluate("window.once"), 1)
        result = await self.page.evaluate("""
            () => {
              let calls = 0;
              const x = {
                n: { value: 3 },
                get nope() {
                  calls++;
                  throw Error("getter");
                },
              };
              x.self = x;
              console.log(x);
              console.log(
                new Proxy(
                  {},
                  {
                    ownKeys() {
                      throw Error("denied");
                    },
                  },
                ),
              );
              return calls;
            }
            """)
        self.assertEqual(result, 0)
        await root.locator(".row").filter(has_text="Circular").wait_for()
        await root.locator(".row").filter(has_text="reflection denied").wait_for()

    async def test_csp_denied_evaluation_is_visible(self):
        await self.page.goto(self.url + "/denied-eval.html")
        root = self.page.locator("#elyon-console")
        await root.locator("#expression").fill("6*7")
        await root.locator("#repl button").click()
        await root.locator(".level-error").wait_for()
        cap = await self.page.evaluate("elyonConsole.snapshot().capabilities.evaluation")
        self.assertEqual(cap["status"], "denied")
        self.assertEqual(cap["reason"], "eval-blocked-by-page-policy")

    async def test_dom_metadata_highlight_invalid_selector_and_storage_edits(self):
        root = self.page.locator("#elyon-console")
        await self.page.evaluate('elyonConsole.showTab("elements")')
        await root.locator("#selector").fill("#inspect-target")
        await root.locator("#selector-form button").first.click()
        meta = json.loads(await root.locator("#element-metadata").inner_text())
        self.assertEqual(meta["id"], "inspect-target")
        self.assertGreater(meta["rect"]["width"], 0)
        await root.locator("#highlight").click()
        self.assertEqual(await root.locator(".element-highlight").count(), 1)
        await root.locator("#selector").fill("[")
        await root.locator("#selector-form button").first.click()
        self.assertIn("SyntaxError", await root.locator("#element-summary").inner_text())
        await self.page.evaluate('elyonConsole.showTab("storage")')
        await root.locator("#storage-key").fill("elyon-regression")
        await root.locator("#storage-value").fill("written-value")
        await root.locator("#storage-form button").click()
        self.assertEqual(
            await self.page.evaluate('localStorage.getItem("elyon-regression")'), "written-value"
        )
        self.page.once("dialog", lambda dialog: dialog.accept())
        await root.get_by_role("button", name="Delete elyon-regression", exact=True).click()
        self.assertIsNone(await self.page.evaluate('localStorage.getItem("elyon-regression")'))

    async def test_storage_denial_and_stylesheet_denial(self):
        await self.reinstall(
            """() => {
                Object.defineProperty(window,'localStorage',{
                    configurable:true,
                    get(){throw new DOMException('blocked','SecurityError')}
                });
            }"""
        )
        await self.page.evaluate('elyonConsole.showTab("storage")')
        self.assertIn(
            "Storage unavailable",
            await self.page.locator("#elyon-console #storage-output").inner_text(),
        )
        self.assertEqual(
            await self.page.evaluate("elyonConsole.snapshot().capabilities.localStorage.status"),
            "denied",
        )
        await self.page.route("**/mobile-console.css", lambda route: route.abort())
        await self.reinstall()
        await self.page.wait_for_function(
            'elyonConsole.snapshot().capabilities.styles.status==="denied"'
        )
        self.assertFalse(self.errors)

    async def test_all_themes_preferences_and_320_through_440_layout(self):
        root = self.page.locator("#elyon-console")
        await self.page.evaluate('elyonConsole.showTab("settings")')
        self.assertEqual(await root.locator("[data-theme]").count(), 20)
        for theme in await root.locator("[data-theme]").all():
            await theme.click()
            self.assertEqual(await theme.get_attribute("aria-pressed"), "true")
        await root.locator("[data-theme=orchid-folio]").click()
        await self.page.reload()
        self.assertEqual(
            await root.locator(".elyon-shell").evaluate('el=>el.style.getPropertyValue("--bg")'),
            "#f8f1fb",
        )
        for width in [320, 360, 375, 390, 414, 430, 440]:
            await self.page.set_viewport_size({"width": width, "height": 844})
            self.assertLessEqual(
                await self.page.evaluate("document.documentElement.scrollWidth"), width
            )
            for selector in [".console", "#tab-settings", "#repl button", "#expression"]:
                box = await root.locator(selector).bounding_box()
                self.assertIsNotNone(box)
                self.assertGreaterEqual(box["x"], -1)
                self.assertLessEqual(box["x"] + box["width"], width + 1)
        # Resizing exercises the real visualViewport resize path; it does not
        # pretend to produce a physical iOS keyboard.
        await root.locator("#expression").focus()
        await self.page.set_viewport_size({"width": 320, "height": 330})
        await self.page.wait_for_timeout(50)
        box = await root.locator("#repl button").bounding_box()
        self.assertLessEqual(box["y"] + box["height"], 330)
        await self.page.set_viewport_size({"width": 320, "height": 180})
        await self.page.wait_for_timeout(50)
        box = await root.locator("#repl button").bounding_box()
        self.assertLessEqual(box["y"] + box["height"], 180)

    async def test_pointer_drag_resize_launcher_and_keyboard_navigation(self):
        root = self.page.locator("#elyon-console")
        box = await root.locator("#move-handle").bounding_box()
        start = await root.locator(".console").bounding_box()
        await self.page.mouse.move(box["x"] + 20, box["y"] + 20)
        await self.page.mouse.down()
        await self.page.mouse.move(box["x"] + 20, box["y"] - 100, steps=5)
        await self.page.mouse.up()
        moved = await root.locator(".console").bounding_box()
        self.assertLess(moved["y"], start["y"])
        await root.locator("#size-handle").focus()
        height = moved["height"]
        await root.locator("#size-handle").press("ArrowUp")
        resized = await root.locator(".console").bounding_box()
        self.assertGreater(resized["height"], height)
        await root.locator("#close").click()
        box = await root.locator(".launcher").bounding_box()
        await self.page.mouse.move(box["x"] + 20, box["y"] + 20)
        await self.page.mouse.down()
        await self.page.mouse.move(25, 100, steps=8)
        await self.page.mouse.up()
        self.assertFalse(await root.locator(".console").is_visible())
        launcher = await root.locator(".launcher").bounding_box()
        self.assertLess(launcher["y"], box["y"])
        await root.locator(".launcher").click()
        self.assertTrue(await root.locator(".console").is_visible())
        await root.locator("#tab-console").focus()
        await root.locator("#tab-console").press("End")
        self.assertEqual(await root.locator("#tab-settings").get_attribute("aria-selected"), "true")

    async def test_redaction_snapshot_integrity_and_no_independent_claim(self):
        await self.page.evaluate(
            'console.error("fixture-secret-123");fetch("/fixture/fail?token=fixture-secret-123")'
        )
        raw = await self.page.evaluate("elyonConsole.snapshot({redacted:false})")
        safe = await self.page.evaluate("elyonConsole.snapshot()")
        self.assertIn("fixture-secret-123", json.dumps(raw))
        self.assertNotIn("fixture-secret-123", json.dumps(safe))
        self.assertEqual(safe["source"], "elyon-page-console")
        self.assertFalse(safe["independentEvidence"])
        self.assertFalse(raw["redacted"])
        self.assertEqual(safe["retention"]["policy"], "volatile-drop-oldest")
        await self.page.evaluate(
            """() => {
                const copy=elyonConsole.snapshot({redacted:false});
                copy.requests.length=0;
                copy.capabilities.fetch.status='fake';
            }"""
        )
        self.assertNotEqual(
            await self.page.evaluate("elyonConsole.snapshot().capabilities.fetch.status"), "fake"
        )
        self.assertGreater(len(await self.rows()), 0)
        async with self.page.expect_download() as result:
            await self.page.locator("#elyon-console #export").click()
        download = await result.value
        path = Path("artifacts/iphone-regression-export.json")
        path.parent.mkdir(exist_ok=True)
        await download.save_as(path)
        self.assertNotIn("fixture-secret-123", path.read_text())

    async def test_static_distribution_manifest_and_no_backend(self):
        manifest = json.loads((ROOT / "dist/iphone-demo/manifest.json").read_text())
        self.assertFalse(manifest["broker"] or manifest["nativeBridge"])
        for name, digest in manifest["assets"].items():
            self.assertEqual(
                hashlib.sha256((ROOT / "dist/iphone-demo" / name).read_bytes()).hexdigest(), digest
            )
        # This Node server is the actual shipped static preview, not the test fixture server.
        proc = subprocess.Popen(
            ["node", "tools/serve-demo.mjs", "--port", "0"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            url = proc.stdout.readline().strip().split()[-1]
            page = await self.browser.new_page()
            responses = []
            page.on("response", lambda response: responses.append(response))
            await page.goto(url)
            await page.locator("#elyon-console .console").wait_for()
            self.assertEqual((await page.request.get(url + "/api/state")).status, 404)
            self.assertEqual((await page.request.post(url + "/command", data="{}")).status, 404)
            self.assertTrue(all(response.status == 200 for response in responses))
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
