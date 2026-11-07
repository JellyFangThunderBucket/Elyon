# iPhone usability baseline — 2026-11-07

Baseline: latest `main`, merge commit `c9c9710` (PR #1 merged). Its active source
is identical to `c2f6a66`; no recovery patches were reapplied. Read README,
VERIFICATION, PRODUCT-DIRECTION, GECKO, REPOSITORY-AUDIT, the executable modules,
protocol/native-design notes, test suites, package metadata, and workflow configuration.
Original uploaded evidence remains separate under `recovery/`.

## Implemented at baseline

- Python independent broker with authenticated loopback control, fsynced bounded
  journals, explicit provenance/gaps, and validated redacted import/export.
- Real Chromium observation/capture harness and deterministic browser fixtures.
- Opt-in Chii target/DevTools integration; no Chii-to-broker adapter.
- Square Shadow DOM page console with six tools, 20 themes, saved preferences,
  bounded previews, a REPL, metadata-only Fetch/XHR wrappers, DOM/storage viewing.
- Source/recovery integrity tooling and CI checks.

## Newly executed baseline results, before source changes

All commands exited 0. Durations are local observations, not performance claims.
The Python commands used the repository's pinned `.venv` development tools.
Loopback workbench/Chii ports were 8780/8781; UI scripts received those URLs.

| Command | Result | Seconds |
| --- | --- | --- |
| `python tools/check_recovery.py` | 84 hashes / 60 ordered patches verified | 0.04 |
| `npm run check:themes` | 20 palettes, minimum checked text contrast 6.03:1 | 0.23 |
| `npm run format:check` | Passed | 0.95 |
| `python -m unittest discover -v` | 41 tests passed | 3.10 |
| `python -m unittest validation.browser_check -v` | Both tests passed; includes 100 redirects, stall/crash | 25.65 |
| `python -m mypy elyon` | Passed, 10 modules | 0.23 |
| `python -m ruff check .` | Passed | 0.05 |
| `python -m ruff format --check elyon tests validation` | Passed | 0.04 |
| `python -m build` | Source distribution and wheel built | 3.66 |
| `python validation/workbench_check.py` | Capture/archive/mobile/actual Chii inspector passed | 16.48 |
| `python validation/mobile_console_check.py` | Existing phone-sized interaction script passed | 4.77 |
| `npm audit --omit=dev` | Zero reported vulnerabilities | 0.62 |

Logs were recorded at `artifacts/baseline/` locally. These are new results; older
recovery RESULT/VALIDATION documents remain historical source records.

## Gaps not covered by those passing checks

A separate real-browser baseline probe reused an XHR inside `onload`. Native
handlers observed `[200, 404]`; the baseline console incorrectly recorded `[0, 0]`.
Its once-only loadend observers read the reused object's new status and could
consume a later request's observer on the previous loadend event.

Other reviewed limitations: no drag/resize gesture or visual-viewport handling;
no standalone static playground (its request button requires `/api/state`);
no explicit pending-XHR listener cleanup; unsafe extra argument coercion/getter
reads in Fetch observation; incomplete denied-capability diagnostics; shallow DOM
metadata and read-only storage; and no regression matrix across 320–440px.

The page console shares the content thread and is volatile. The broker remains a
separate desktop-hosted component. No iPhone, Safari/WebKit, Reynard/Gecko native,
remote pairing, or real iOS keyboard validation was performed at this baseline.
