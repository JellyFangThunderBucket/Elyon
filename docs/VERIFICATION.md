# Verification for the organized mobile console

Validated in the managed Linux environment on 2026-11-07. These are current
results, separate from historical recovered RESULT/VALIDATION records.

| Check | Result |
| --- | --- |
| Original upload integrity | All 84 uploaded files match their SHA-256 records; all 60 patches accounted for |
| Pinned-tool unit suite | 41 tests passed |
| Real Chromium acceptance | Both tests passed, including 100 redirect iterations, stall/crash controls, service worker, CSP, frames/workers, and late-response identity |
| Workbench integration | Capture, filters, row detail, export/import, mobile layout, Chii target registration, and actual DevTools Elements window passed |
| Mobile console integration | 20 themes, saved preferences, REPL/toggle, console capture, Fetch/XHR, DOM, storage, redacted export, bounded retention, and conditional teardown passed |
| Browser page errors | None in the tested workbench/mobile flows |
| Palette check | 20 unique original palettes; minimum checked text contrast 6.03:1 on background/surface at full opacity |
| Ruff / strict mypy | Passed with the repository's pinned development versions |
| npm runtime audit | Zero reported vulnerabilities with pinned transitive overrides |
| Python distribution | Source archive and wheel built; static console assets included |

Browser tests used system Chromium with `chromium_sandbox=True`. The mobile UI
checks emulate a 390 × 844 touch viewport; they are not physical iPhone or native
WebKit/Gecko validation. No iOS engine binary was built in this Linux environment.
Eruda npm 3.4.3 was opened separately for live Settings comparison and was not
added as an Elyon dependency.

The shared browser tool could not initialize its requirements, so there is no
claim that a user-visible shared Chrome tab was opened. Automated Chromium ran
successfully. The checked-in images show that tested console:

| Console | Settings |
| --- | --- |
| ![Phone console](images/mobile-console.png) | ![Phone Settings](images/mobile-settings.png) |

## Reproduce

Use the startup steps in README.md. Run `npm start` and `npm run chii`, then:

```sh
python tools/check_recovery.py
npm run check:themes
npm run format:check
python -m unittest discover -v
python -m unittest validation.browser_check -v
python validation/workbench_check.py
python validation/mobile_console_check.py
python -m ruff check .
python -m mypy elyon
python -m build
```

For alternative local test ports, set `ELYON_TEST_BASE_URL` and
`ELYON_TEST_CHII_URL` for the UI scripts. Tests intentionally fail rather than
silently skip when required browser/server capabilities are missing.
