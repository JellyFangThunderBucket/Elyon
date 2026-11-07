"""Exercise the running local workbench and real Chii target/inspector connection."""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

BASE = os.environ.get("ELYON_TEST_BASE_URL", "http://127.0.0.1:8080")


CHII = os.environ.get("ELYON_TEST_CHII_URL", "http://127.0.0.1:8090")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=(
                None
                if os.getenv("ELYON_CHROMIUM_EXECUTABLE") == "bundled"
                else os.getenv("ELYON_CHROMIUM_EXECUTABLE", "/usr/bin/chromium")
            ),
            chromium_sandbox=True,
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(BASE)
        run_ids = []
        for _ in range(2):
            async with page.expect_response(
                lambda response: response.url.endswith("/api/run")
            ) as posted:
                await page.get_by_role("button", name="Run browser capture").click()
            payload = await (await posted.value).json()
            run_ids.append(payload["run"])
            await page.wait_for_function(
                """run => {
                const status=document.querySelector('#status');
                return status.dataset.run===run && status.textContent===
                    'Evidence survived the renderer crash';
            }""",
                arg=payload["run"],
                timeout=60000,
            )
            assert await page.locator("#observations").inner_text() != "0"
        assert run_ids[0] != run_ids[1]
        await page.locator("tbody tr").first.click()
        assert "RequestAttempt" in await page.locator("#json").inner_text()
        await page.locator("#search").fill("impossible-resource")
        await page.get_by_text("No matching observations.").wait_for()
        await page.locator("#search").fill("")
        async with page.expect_download() as download:
            await page.locator("#export").click()
        archive = await download.value
        file = Path("artifacts/ui-export.json")
        await archive.save_as(file)
        await page.locator("#import").set_input_files(str(file))
        await page.get_by_text("Archive opened locally", exact=True).wait_for()
        await page.screenshot(path="artifacts/workbench-desktop.png", full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path="artifacts/workbench-mobile.png", full_page=True)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        demo = await browser.new_page()
        await demo.goto(BASE + "/demo")
        await demo.evaluate("window.elyonConsole.close()")
        await demo.locator("#server").fill(CHII)
        await demo.get_by_role("button", name="Connect Chii", exact=True).click()
        await demo.get_by_text("Chii script loaded.", exact=False).wait_for()
        inspector = await browser.new_page()
        await inspector.goto(CHII)
        await inspector.get_by_text("Elyon playground", exact=False).first.wait_for(timeout=20000)
        await demo.locator("#counter").click()
        assert await demo.locator("#counter").inner_text() == "Count: 1"
        await demo.locator("#request").click()
        await demo.locator("#output").filter(has_text="snapshot").wait_for()
        await inspector.screenshot(path="artifacts/chii-target.png", full_page=True)
        async with inspector.expect_popup() as popup:
            await inspector.get_by_text("inspect", exact=True).click()
        devtools = await popup.value
        await devtools.get_by_role("tab", name="Elements", exact=True).wait_for(timeout=30000)
        print(
            json.dumps(
                {
                    "browserErrors": errors,
                    "uiCapture": True,
                    "importExport": True,
                    "mobileLayout": True,
                    "chiiTargetConnected": True,
                }
            )
        )
        assert not errors, errors
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
