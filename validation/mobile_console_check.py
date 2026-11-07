"""Phone-sized integration checks for real console behavior and all theme palettes."""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("ELYON_TEST_BASE_URL", "http://127.0.0.1:8080")


async def main():
    Path("artifacts").mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=(
                None
                if os.getenv("ELYON_CHROMIUM_EXECUTABLE") == "bundled"
                else os.getenv("ELYON_CHROMIUM_EXECUTABLE", "/usr/bin/chromium")
            ),
            chromium_sandbox=True,
        )
        page = await browser.new_page(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        await page.add_init_script("""window.elyonOriginals = {
            log: console.log, open: XMLHttpRequest.prototype.open,
            send: XMLHttpRequest.prototype.send
        };""")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE + "/demo")
        console = page.locator("#elyon-console")
        await console.locator(".console").wait_for()
        settings = console.locator("[data-tab=settings]")
        assert await settings.is_visible()
        box = await settings.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= 390
        await settings.click()
        assert await console.locator("[data-theme]").count() == 20
        for button in await console.locator("[data-theme]").all():
            await button.click()
            assert await button.get_attribute("aria-pressed") == "true"
            tokens = await console.locator(".elyon-shell").evaluate(
                '(el)=>["bg","fg","accent"].map(k=>el.style.getPropertyValue("--"+k))'
            )
            assert all(tokens)
        await console.get_by_role("button", name="Orchid Folio", exact=True).click()
        await console.locator("#setting-fontSize").fill("17")
        await console.locator("#setting-fontSize").dispatch_event("input")
        await page.reload()
        await page.locator("#elyon-console .console").wait_for()
        await settings.click()
        assert (
            await console.get_by_role("button", name="Orchid Folio").get_attribute("aria-pressed")
            == "true"
        )
        assert await console.locator("#setting-fontSize").input_value() == "17"
        await page.screenshot(path="artifacts/mobile-themes.png", full_page=True)
        await console.locator("[data-theme=basalt-circuit]").click()
        await console.locator("#setting-jsExecution").uncheck()
        await console.locator("[data-tab=console]").click()
        assert await console.locator("#expression").is_disabled()
        await settings.click()
        await console.locator("#setting-jsExecution").check()
        await console.locator("[data-tab=console]").click()
        await console.locator("#expression").fill("Promise.resolve(6 * 7)")
        await console.locator("#repl button").click()
        await console.locator(".level-result").filter(has_text="42").wait_for()
        await page.evaluate('console.warn("mobile-warning-check")')
        await console.locator(".level-warn").filter(has_text="mobile-warning-check").wait_for()
        await page.evaluate("""() => {
            const object = {};
            Object.defineProperty(object, 'danger', {
                enumerable: true, get() { throw new Error('Getter must not run'); }
            });
            console.log(object);
        }""")
        await console.locator(".row").filter(has_text="getter not invoked").wait_for()
        assert await page.evaluate('fetch("/api/state").then(r=>r.status)') == 200
        assert (
            await page.evaluate("""() => new Promise(resolve => {
            const xhr=new XMLHttpRequest();xhr.open('GET','/api/state');
            xhr.onload=()=>resolve(xhr.status);xhr.send();
        })""")
            == 200
        )
        await console.locator("[data-tab=network]").click()
        await console.locator(".request").nth(1).wait_for()
        assert await console.locator(".request").count() == 2
        assert "200" in await console.locator("#requests").inner_text()
        await console.locator("[data-tab=elements]").click()
        await console.locator("#selector").fill("#counter")
        await console.locator("#selector-form button").first.click()
        assert "Count: 0" in await console.locator("#element-output").inner_text()
        await console.locator("#selector").fill("[")
        await console.locator("#selector-form button").first.click()
        assert "SyntaxError" in await console.locator("#element-summary").inner_text()
        await page.evaluate('localStorage.setItem("mobile-proof", "stored-value")')
        await console.locator("[data-tab=storage]").click()
        assert "stored-value" in await console.locator("#storage-output").inner_text()
        await settings.click()
        await console.locator("#reset").click()
        assert await page.evaluate('localStorage.getItem("mobile-proof")') == "stored-value"
        await console.locator("[data-tab=console]").click()
        await page.evaluate('console.error("demo error with private token secret-value")')
        async with page.expect_download() as result:
            await console.locator("#export").click()
        download = await result.value
        await download.save_as("artifacts/mobile-session-redacted.json")
        data = json.loads(Path("artifacts/mobile-session-redacted.json").read_text())
        assert data["redacted"] and "secret-value" not in json.dumps(data)
        await page.screenshot(path="artifacts/mobile-console.png", full_page=True)
        await settings.click()
        await console.locator("#setting-maxRows").select_option("100")
        await console.locator("[data-tab=console]").click()
        await page.evaluate("() => {for(let n=0;n<1000;n++)console.log('bounded-log',n)}")
        await console.locator("#row-count").filter(has_text="100 logs").wait_for()
        assert await console.locator("#logs .row").count() == 100
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        # Instrumentation is removable and does not discard wrappers installed later by a page.
        assert await page.evaluate("""() => {
            const old = fetch;
            const later = (...args) => old(...args);
            window.fetch = later;
            window.elyonConsole.destroy();
            return window.fetch === later && !document.querySelector('#elyon-console')
                && console.log === window.elyonOriginals.log
                && XMLHttpRequest.prototype.open === window.elyonOriginals.open
                && XMLHttpRequest.prototype.send === window.elyonOriginals.send;
        }""")
        await page.goto(BASE)
        await page.locator("[data-view=settings]").click()
        await page.get_by_role("button", name="Glacier Paper", exact=True).click()
        await page.reload()
        assert (
            await page.locator("html").evaluate('el => el.style.getPropertyValue("--bg")')
            == "#f1f8fc"
        )
        assert not errors, errors
        print(
            json.dumps(
                {
                    "themes": 20,
                    "settingsPersist": True,
                    "fetchAndXHR": True,
                    "consoleAndREPL": True,
                    "DOMAndStorage": True,
                    "redactedExport": True,
                    "teardown": True,
                    "browserErrors": errors,
                }
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
