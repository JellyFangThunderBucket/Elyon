# iPhone usability change manifest

This continuation is based on merged main `c9c9710`. Functioning broker, journal,
protocol, graph, handle storage, recovery files, and the 20 palette definitions
are preserved. The desktop harness only gains configurable browser selection;
workbench changes prevent stale capture status and serve the new module assets.

See [verification](VERIFICATION.md), [device instructions](IPHONE-TESTING.md),
and [page-observation semantics](PAGE-INSTRUMENTATION.md).

| Change | File |
| --- | --- |
| Modified | `.github/workflows/checks.yml` |
| Added | `.github/workflows/device-demo.yml` |
| Modified | `MANIFEST.in` |
| Modified | `README.md` |
| Added | `docs/BASELINE-IPHONE.md` |
| Added | `docs/CHANGES-IPHONE.md` |
| Modified | `docs/GECKO.md` |
| Added | `docs/IPHONE-TESTING.md` |
| Added | `docs/PAGE-INSTRUMENTATION.md` |
| Modified | `docs/PRODUCT-DIRECTION.md` |
| Modified | `docs/REPOSITORY-AUDIT.md` |
| Modified | `docs/VERIFICATION.md` |
| Added | `docs/images/iphone-network.png` |
| Modified | `docs/images/mobile-console.png` |
| Modified | `docs/images/mobile-settings.png` |
| Modified | `elyon/desktop.py` |
| Modified | `elyon/web/app.js` |
| Added | `elyon/web/device-demo.css` |
| Added | `elyon/web/device-demo.html` |
| Added | `elyon/web/device-demo.js` |
| Added | `elyon/web/fixtures/response.json` |
| Modified | `elyon/web/index.html` |
| Modified | `elyon/web/mobile-console.css` |
| Modified | `elyon/web/mobile-console.js` |
| Added | `elyon/web/network.js` |
| Added | `elyon/web/page-runtime.js` |
| Modified | `elyon/workbench.py` |
| Modified | `package-lock.json` |
| Modified | `package.json` |
| Modified | `pyproject.toml` |
| Added | `tools/build-demo.mjs` |
| Added | `tools/run_browser_checks.py` |
| Added | `tools/serve-demo.mjs` |
| Added | `validation/iphone_regression.py` |
| Modified | `validation/mobile_console_check.py` |
| Modified | `validation/workbench_check.py` |
