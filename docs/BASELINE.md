> Historical recovered record. For current layout and validation, see
> [the repository audit](REPOSITORY-AUDIT.md) and [current product direction](PRODUCT-DIRECTION.md).

# Baseline and feasibility

Inspection before source changes (2026-11-06, client date):

* `/workspace/Elyon`, branch `work`, HEAD
  `5e16f5f5ffdef5c56a951d045b3a4868bd2bb821`: one initial commit,
  one tracked file (`README.md`, 20 bytes), clean working tree. All local refs
  examined; no previous implementations or test failures exist to reuse.
* No Gecko checkout/embedding/fork/RDP integration, WKWebView host, injected
  console, app, settings, dependency declarations, builds, tests, or agent instructions.
* Linux x86_64, Python 3.12.14, Node 24.22.1, system Chromium 156.0.8078.79,
  Playwright 1.62.0. No Firefox binary, Xcode, xcrun, iOS simulator or attached
  iPhone tooling. Native signing/JIT/process isolation cannot be tested here.
* Shared architecture conversation and Apple's alternative-browser-engine support
  page both fail through the proxy with CONNECT 403. The supplied directive is
  authoritative. Current jurisdiction, OS-version, entitlement, distribution,
  signing, JIT and process-model requirements remain **unverified external gates**;
  this implementation must not be interpreted as iPhone feasibility evidence.
* Eruda inspected separately in `/tmp/elyon-eruda-reference`, revision
  `0c55928fec802fb2102934c4b5928686178b467b` (3.4.3): mobile in-page tools,
  Network, Settings, Console, Elements, Karma/Jasmine, webpack. None of its source,
  assets, styles, dependencies or tests are copied into Elyon. In-page inspection
  cannot establish stall-independent native observation.

Decision: implement a Python broker process and a fresh desktop Chromium/Playwright
validation adapter. Gecko remains research pending a pinned, buildable upstream
revision and verified actors. No Gecko commands are invented. A separate capability
declaration must continue to report native Gecko and native message identity unsupported.

Required local checks: broker regression suite, build, strict typecheck, lint,
real sandbox-enabled Chromium response/redirect/stall/termination harness.
Optional and unavailable: iOS execution and native performance targets.
