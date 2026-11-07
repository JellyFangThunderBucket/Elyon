# Elyon

A recovered developer-tools foundation, now with a working visual workbench and
an opt-in [Chii](https://github.com/liriliri/chii) live inspector.

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

Open **http://127.0.0.1:8080**. Click **Run browser capture** to exercise actual
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

## What this release actually does

- Authenticated loopback evidence broker with an append-only, fsynced journal.
- Immutable observations and explicit provenance relationships, gaps, and unknowns.
- Real Chromium validation, including independent controls during content stalls.
- Responsive visual workbench, archive viewing, and redacted exports.
- Pinned Chii server, connection instructions, and an opt-in live playground.

This is a desktop-tested foundation for mobile devtools. **It is not yet a native
iOS app.** WebKit/Safari device validation, native bridges, authenticated remote
pairing, and a Chii-to-broker evidence adapter remain to be implemented. Chii
cannot inspect arbitrary iOS apps or bypass Safari restrictions.

## Verify

```sh
python -m unittest discover -v
python -m unittest validation.browser_check -v
python -m mypy elyon
python -m ruff check .
python -m ruff format --check elyon tests validation
python -m build
# With npm start and npm run chii running:
python validation/workbench_check.py
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
