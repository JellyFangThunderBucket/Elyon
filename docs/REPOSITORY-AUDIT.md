# Repository audit and canonical layout

Audited the repository at `cc96029d7a0ca81e2df33c3c0c64bf8479aae8b7`.
The root contained 84 uploaded files: historical source snapshots, 60 patches,
documentation, and a recovery ZIP. Python package metadata, a package directory,
and the visual workbench were absent from the root; they were present in the ZIP
and the previously reconciled local commit `4daa623`.

The active tree was restored from that tested commit, rather than treating the
flattened snapshots as final code or replaying ambiguous patches blindly.

| Path | Purpose |
| --- | --- |
| `elyon/` | Canonical Python broker, CLI, browser harness, and HTTP workbench |
| `elyon/web/` | Workbench, original page console, themes, and playground |
| `tests/` | Broker, protocol, journal, transport, and scenario tests |
| `validation/` | Browser and mobile-sized integration checks |
| `tools/` | Recovery integrity and palette contrast checks |
| `docs/` | Current architecture, research, and historical engineering records |
| `recovery/` | Byte-for-byte original uploads; not active application source |
| `artifacts/` | Ignored generated captures, reports, exports, and screenshots |

`recovery/UPLOAD-MAP.json` accounts for every uploaded file with an old path,
preserved path, and SHA-256. `python tools/check_recovery.py` verifies all 84.
No uploaded evidence was discarded. The bundle remains in Git because it was
already uploaded; generated future bundles should be release artifacts.

## Missing pieces restored

- `pyproject.toml`, `MANIFEST.in`, npm package and lockfile, and `.gitignore`.
- Correct package/test/validation directories and `tests/__init__.py`.
- The reconciled broker fixes, which were absent from initial snapshots.
- Workbench assets, current setup instructions, and verification workflow.

## Remaining limitations

The original lost final tree cannot be proved byte-identical from incomplete
patch evidence. This continuation is validated behaviorally. iOS native bridges,
secure remote pairing, and a Chii-to-broker adapter are not present. The independent
broker currently runs in Python on a desktop. The new page console can be served
as static ES modules, but the workbench's capture API requires the Python host.

The workflow checks source, recovery hashes, palette contrast, formatting,
unit tests, typing, and packaging. Real browser checks are explicit commands;
they require system Chromium with its sandbox enabled and the workbench/Chii
servers where indicated. Nothing substitutes emulation for physical iPhone tests.

## iPhone usability continuation

The current page-console work builds on merged main `c9c9710`; the new baseline
is documented in BASELINE-IPHONE.md. `network.js` and `page-runtime.js` isolate
page-level observation helpers. The standalone device lab is built by
`tools/build-demo.mjs` into `dist/iphone-demo/`. It contains no Python API, broker,
Chii server, or credentials. Browser regressions are reproducible with
`python tools/run_browser_checks.py`; deployment remains a separate manual workflow.
