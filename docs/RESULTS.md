> Historical recovered record. For current layout and validation, see
> [the repository audit](REPOSITORY-AUDIT.md) and [current product direction](PRODUCT-DIRECTION.md).

# Execution results

Baseline: one README and initial commit `5e16f5f`; no implementation, previous
versions, test infrastructure or uncommitted work. See [baseline](BASELINE.md).
All implementation is new; no Eruda files, assets or dependencies were copied.

## What now executes

An independent Python broker process accepts `elyon-observer/0.1`, journals immutable
evidence before acknowledgment, projects an explicit provenance graph and serves
authenticated loopback inspection/export commands. The desktop adapter records
actual Chromium/Playwright observations. Synthetic tests identify themselves as such.

The real response claim demonstrated: 100 repeated `/redirect` → `/ok` browser
requests retain both response versions and a redirect-to edge supported by actual
`Request.redirected_from` identity. Delivered evidence survives an actual renderer
crash. Twelve broker control/export operations complete during a five-second content
busy loop. This is **desktop Chromium evidence**, not native Gecko/iPhone validation.

## Final command results

All commands ran from `/workspace/Elyon` using `.venv/bin/python` and the pinned
development tools. Final invocations after fixes:

| Command | Actual result | Exit |
|---|---|---|
| `python -m unittest discover -v` | `Ran 41 tests in 1.763s`, `OK` | 0 |
| `python -m unittest validation.browser_check -v` | `Ran 2 tests in 19.892s`, `OK` | 0 |
| `python -m mypy elyon` | `Success: no issues found in 9 source files` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `15 files already formatted` | 0 |
| `python -m build --no-isolation` | built sdist and `elyon_observer-0.1.0-py3-none-any.whl` | 0 |
| `git diff --check` | no whitespace errors | 0 |

Real checks used sandbox-enabled system Chromium **156.0.8078.79** on Linux x86_64.
They ran outside the nested command sandbox because Chromium's sandbox helper
could not initialize inside it. Browser sandbox protections were retained.

The final browser suite also validates cache/revalidation stimuli, SW handling flag,
CSP blocked Fetch, nested frame/worker completion, unknown child identities, a
response crossing a generation transition, and a disconnected request. It does not
claim raw wire 304, cache origin, native policy decisions or page-visible exposure
from those observations. No tests are silently skipped. No known failing regression
remains in these suites.

## Files changed

* `README.md`: execution and inspection instructions, scope.
* `.gitignore`, `pyproject.toml`, `MANIFEST.in`: package/build/dev tools and artifact separation.
* `elyon/__init__.py`: package boundary.
* `elyon/protocol.py`: strict message/envelope validation, decimal uint64, deterministic IDs.
* `elyon/journal.py`: bounded append-only single-writer fsynced storage, explicit torn-tail errors.
* `elyon/handles.py`: bounded local handles, expiry, release, unsupported fields.
* `elyon/broker.py`: capture/target/activation lifecycle, sequence gaps, credit, immutable
  graph snapshots, conservative redaction, replay-validated portable import/export.
* `elyon/graph.py`: projection without speculative relationships.
* `elyon/cli.py`: authenticated, bounded-concurrency loopback controls; restricted client;
  no inspected-content call in the control path.
* `elyon/desktop.py`: original public-API Chromium observation adapter and executable acceptance host.
* `elyon/fixtures.py`: deterministic local HTTP, SW, frame, worker, CSP, stall-related stimuli.
* `tests/__init__.py`, `tests/test_foundation.py`, `tests/test_broker.py`,
  `tests/test_host.py`, `tests/test_scenarios.py`: 41 synthetic/unit/process regressions.
* `validation/browser_check.py`: two explicit real-browser acceptance checks.
* `docs/BASELINE.md`, `docs/PROTOCOL.md`, `docs/VALIDATION.md`, `docs/CAUSAL_HANDOFF.md`,
  `docs/RESULTS.md`, `docs/superpowers/plans/2026-11-06-observation-foundation.md`:
  facts, contract, limitations, hook dependency, outcomes and execution scope.

Generated evidence is ignored by Git: `artifacts/desktop-100/` contains the preserved
100-run report, raw journal/snapshot, redacted archive and during-stall export;
`artifacts/fixtures-reviewed/` contains the expanded reviewed-fixture archive and
report. The acceptance tests also run in temporary directories and clean up their
processes. A preserved real archive was reimported successfully: 503 nodes and 301
relationships, with incomplete capture status retained.

## Review and remaining gates

Independent review found seven important issues: structural-rule redaction leakage,
ended-generation reuse, producer Gap coverage, late-response generation attribution,
idle-connection blocking, nonloopback/redirect credential routing, and imported-file
permissions. Each received a failing regression followed by a fix and a green suite.
A subsequent disconnected-request regression caught and fixed an adapter reference
shape error. A transient nested-worker console wait timed out once; durable fixture
completion state now replaces it and the complete browser suite passes. The minor
target-limit documentation error was corrected; no deferred minor finding remains.

Engineering decisions: use the current isolated checkout, a Python process boundary
and desktop Chromium host to obtain real evidence without an unavailable native
engine. No iPhone/simulator/native UI or native performance targets are verified.
Gecko remains **research-only pending narrower pinned-revision actor validation**.
Apple permission/signing/JIT/process/deployment requirements remain external gates.
See [limitations](VALIDATION.md) and [causal hook dependency](CAUSAL_HANDOFF.md).

Smallest next implementation: one verified native RequestAttempt/ResponseVersion
producer against a pinned, buildable desktop Gecko revision, reusing this contract.
Do not enable native causal tracing until an actual message-operation identity hook
has been verified. No commits, pushes or environment publication were performed.
