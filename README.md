# Elyon

A recovered developer-tools foundation, now with a working visual workbench and
an opt-in [Chii](https://github.com/liriliri/chii) live inspector.

The repository is now organized: active source lives in `elyon/`, tests in
`tests/`, documentation in `docs/`, and all original uploads are preserved under
`recovery/`. See [the repository audit](docs/REPOSITORY-AUDIT.md).

## Try it

Requirements: Python 3.12+, Node 20+, and sandbox-capable system Chromium at
`/usr/bin/chromium` (the browser capture harness uses Playwright).

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
npm ci
npm start
```

Open **http://127.0.0.1:8080/demo** for the square mobile page console. Settings
is pinned beside the scrollable tool tabs and includes 20 original themes. Try
Console, Network, Elements, Storage, and Info. Preferences persist on this origin.

Open **http://127.0.0.1:8080** for the independent evidence workbench. Click **Run browser capture** to exercise actual
redirects, a five-second page stall, independent broker controls, and renderer
termination. Inspect individual observations, filter requests, and export a
redacted archive. Import opens an archive in the browser after a digest check;
use the CLI import for complete semantic replay validation.

In a second terminal:

```sh
npm run chii
```

Choose **Live inspection → Open playground**, then **Connect Chii** in the
playground. Open **http://127.0.0.1:8090**, select the Elyon playground target,
and click Inspect. The counter and Fetch buttons provide inspectable activity.
Chii's script is loaded only after choosing Connect.

Both services default to loopback. To connect an iPhone on a trusted LAN, run
`npx chii start -h 0.0.0.0 -p 8090 -d YOUR_LAN_IP:8090` and use
`http://YOUR_LAN_IP:8090` in the generated script on a page you control.
HTTPS pages require an HTTPS/WSS endpoint and appropriate CSP permissions.
Chii has no authentication by default: do not expose that server publicly.
Its JavaScript instrumentation can change page behavior. It is separate from
Elyon's metadata-only browser harness and durable evidence broker.

## Use the page console on a development page

Serve the three assets `mobile-console.js`, `mobile-console.css`, and `themes.js`
from an origin your page permits, keeping them in the same directory. Then:

```html
<script type="module">
  import { createConsole } from "/devtools/mobile-console.js";
  createConsole().open();
</script>
```

The console instruments console methods, Fetch, and XHR in that page; this may
change timing and function identity. It does not capture response bodies. Use
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
python -m unittest discover -v
python -m unittest validation.browser_check -v
python -m mypy elyon
python -m ruff check .
python -m ruff format --check elyon tests validation
python -m build
# With npm start and npm run chii running:
python validation/workbench_check.py
python validation/mobile_console_check.py
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
