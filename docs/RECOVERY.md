# Recovery and visible workbench — 2026-11-07

## Evidence and reconstruction

The user supplied `1-Elyon_recovery_evidence.zip`, containing initial snapshots
and 60 ordered change records across 24 file basenames. The archive warns that
these are not a provably complete final tree. The linked prior chat could not
be read because this session exposes no `read_thread` tool. No claims are made
about unseen messages or files.

Original evidence was extracted separately at `/workspace/recovery-evidence`.
Reconstruction began with the supplied initial sources. Context matching recovered
most hunks; formatting differences required a second pass. Remaining gaps were
reconciled by reading the changes and exercising the supplied tests. Changes
include restoring `secrets.token_urlsafe(32)` where evidence had a `<SECRET>`
placeholder; placing the 16 MiB journal test in its intended test class; restoring
atomic endpoint publication, bounded server concurrency, loopback-only client
validation, canonical gap records, and owner-only imports; and preserving the
original request target for late responses and termination references.

Formatting-only changes split across the recorded patches are not reproduced
byte-for-byte. This is a reconciled, tested continuation, not a claim of exact
recovery of the lost final bytes. `tests/__init__.py`, absent from the archive,
was restored to enable default unittest discovery.

## Added now

`elyon.workbench` serves a local responsive interface at port 8080. Captures launch
the existing deterministic harness in a separate process, with a new artifact
directory for every run. The UI polls the authenticated broker during a run and
reads its completed snapshot afterward. Imported archives stay in the browser;
a digest check detects modification but is not full semantic replay validation.
Use the CLI importer for that guarantee. Data is rendered using textContent.

The npm lockfile pins Chii 1.15.5. Its inspector runs independently on loopback
port 8090. The playground loads its target script only after Connect, and tests
verify actual target registration. Chii observations are not ingested into the
Elyon journal yet. Native iOS and WebKit claims remain explicitly unverified.

## Current verification

- 41 recovered unit tests passed.
- Two real-browser acceptance tests passed, including 100 redirect iterations,
  service worker and nested worker fixtures, CSP failure, late-response identity,
  independent controls during a 5-second stall, and renderer termination.
- Workbench browser check passed: capture, search, row detail, redacted download,
  archive reopening, a 390 px mobile layout, and actual Chii target connection.
- Ruff and strict mypy passed for the restored code and workbench.
- Chromium sandbox remained enabled throughout browser tests.
- The source distribution and wheel built successfully.
- `npm audit --omit=dev` reports zero vulnerabilities after explicit uuid 11.1.1
  and qs 6.17.1 overrides; UI/Chii checks passed again with those versions.

The shared CUA browser runtime returned `Browser runtime unavailable`; automated
Playwright with system Chromium worked. Screenshots are saved under artifacts.
Local URLs refer to the execution environment and are not public hosted links.

## Next implementation gates

1. Validate Chii against a physical iPhone Safari page with HTTPS and explicit CSP.
2. Implement authenticated, scoped remote pairing before remote hosting.
3. Add a Chii adapter whose source/capability flags keep page instrumentation
   separate from browser/native observations and preserve disconnect gaps.
4. Choose and validate a native WebKit bridge and iOS delivery model on macOS.

Aspirations such as “best mobile devtools” require device measurements and
comparative evaluation; the recovered desktop tests cannot establish that claim.
