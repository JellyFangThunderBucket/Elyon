# Elyon

A recovered developer-tools foundation, now with a working visual workbench and
an opt-in [Chii](https://github.com/liriliri/chii) live inspector.

The repository is now organized: active source lives in `elyon/`, tests in
`tests/`, documentation in `docs/`, and all original uploads are preserved under
`recovery/`. See [the repository audit](docs/REPOSITORY-AUDIT.md).

## Try the standalone phone console

The deployable device lab needs only static HTTPS hosting. Python, the broker,
and Chii are not required to display or exercise its tools.

```sh
npm ci
npm run build:demo
npm run preview:demo
# Desktop preview: http://127.0.0.1:4173
```

For your iPhone, follow [the exact HTTPS deployment and device-test instructions](docs/IPHONE-TESTING.md).
The manual **Publish static iPhone demo** GitHub Actions workflow deploys only
`dist/iphone-demo/` after Pages is enabled. No deployment URL is claimed live by
this source change. The local preview binds to loopback and is not a phone URL.

The square console supports dragging/resizing, visual-viewport layout, Console,
Fetch/XHR metadata, Elements picking/metadata/highlighting, Storage editing, Info
capability states, and all 20 existing themes. Use JS or Await mode for evaluation.
It observes only the document in which it is installed.

## Independent evidence workbench

The desktop broker/capture harness still requires Python 3.12+, Node 20+, system
Chromium (`/usr/bin/chromium` by default), and Playwright. Keep it separate from
public static hosting:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
npm ci
npm start
# http://127.0.0.1:8080
# Optional second terminal:
npm run chii
# http://127.0.0.1:8090
```

Use **Run browser capture** for actual redirects, a five-second stall, independent
controls, and renderer termination. The workbench ties each status to its current
run ID; repeated captures cannot reuse a previous run's success display.
`/demo` retains the opt-in Chii playground for local integration testing. Chii binds
to loopback by default. Do not publish unauthenticated Chii or broker endpoints.

## Use the page console on a development page

Serve the five assets `mobile-console.js`, `mobile-console.css`, `network.js`,
`page-runtime.js`, and `themes.js`
from an origin your page permits, keeping them in the same directory. Then:

```html
<script type="module">
  import { createConsole } from "/devtools/mobile-console.js";
  createConsole().open();
</script>
```

The console instruments console methods, Fetch, and XHR in that page; this may
change timing and function/Promise identity. See [the instrumentation contract](docs/PAGE-INSTRUMENTATION.md)
for event ordering, reuse, cleanup, retention, and observation limits. It does not capture response bodies. Use
`window.elyonConsole.destroy()` to remove it. Settings affect only that origin.
Storage viewing exposes page values locally; exported sessions redact messages
and URLs. JavaScript execution can be disabled in Settings. The overlay does not
execute code in a remote Chii target.

The Python workbench binds to loopback, so its localhost URL is not a phone or
public preview URL. For real-phone page-console use, serve these static assets
from a trusted HTTPS development host reachable by the phone and permitted by
the page CSP. The overlay shares the page thread; the broker is independent.

## What this release actually does

- Authenticated loopback evidence broker with an append-only, fsynced journal.
- Immutable observations and explicit provenance relationships, gaps, and unknowns.
- Real Chromium validation, including independent controls during content stalls.
- Square mobile page console, 20 original themes, persistent Settings, and live tools.
- Responsive visual workbench, archive viewing, and redacted exports.
- Pinned Chii server, connection instructions, and an opt-in live playground.

This is a desktop-tested foundation for mobile devtools. **It is not yet a native
iOS app.** WebKit/Safari device validation, native bridges, authenticated remote
pairing, and a Chii-to-broker evidence adapter remain to be implemented. Chii
cannot inspect arbitrary iOS apps or bypass Safari restrictions.

## Verify

Run the following from a Git checkout. The recovery integrity check requires the
original uploads, which are intentionally excluded from the Python distribution.

```sh
python tools/check_recovery.py
npm run check:themes
npm run format:check
npm run build:demo
python -m unittest discover -v
python tools/run_browser_checks.py
python -m mypy elyon
python -m ruff check .
python -m ruff format --check elyon tests validation
python -m build
# The runner owns its loopback workbench/Chii and executes:
# python -m unittest validation.browser_check -v
# python -m unittest validation.iphone_regression -v
# python validation/workbench_check.py
# python validation/mobile_console_check.py
```

Keep Chromium's sandbox enabled. In a nested execution sandbox, launch browser
checks with the environment's approved outer-executor command mechanism.
Do not substitute `--no-sandbox`.

Raw captures and logs remain in ignored `artifacts/` directories. Each workbench
run uses a fresh directory; exports remove free-form observed payload fields.
Source, lockfiles, and recovery notes belong in Git. Save the supplied recovery
ZIP outside this temporary environment as well.

See [recovery and current verification](docs/RECOVERY.md),
[protocol](docs/PROTOCOL.md), and [native integration gates](docs/CAUSAL_HANDOFF.md).
The older RESULTS and VALIDATION documents are recovered historical evidence;
the current recovery report distinguishes newly rerun checks.

Read [the product direction](docs/PRODUCT-DIRECTION.md) for the phone walkthrough
and [the Gecko integration research](docs/GECKO.md) for Reynard, native adapter
boundaries, Apple engine pathways, and physical-device acceptance gates.

The newly verified baseline is [recorded separately](docs/BASELINE-IPHONE.md).
No physical iPhone, iOS 27 keyboard, native Gecko, or privileged Safari validation
is claimed. See [current verification](docs/VERIFICATION.md) for exact results.
