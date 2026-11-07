# Open and test Elyon on an iPhone

This is a static, page-level developer console. You can open the same HTTPS page
in Safari or Reynard on your iOS 27 phone. That is an intended manual test path,
not a claim that this release was tested on physical iOS 27 hardware.

## Deploy the standalone demo with GitHub Pages

1. Merge the development pull request into this repository's `main` branch.
2. In GitHub, open **Settings → Pages → Build and deployment → Source** and choose
   **GitHub Actions**. This requires repository administration access.
3. Open **Actions → Publish static iPhone demo → Run workflow**, choose `main`,
   and run it. Approve the `github-pages` deployment environment if your repository
   requires that review.
4. Wait for the deployment job to succeed. Open the **page URL returned by that
   job** on your iPhone. For a standard project site without a custom domain, it
   is normally `https://jellyfangthunderbucket.github.io/Elyon/`.
5. Open that URL separately in Safari and Reynard. If you see a loading/installation
   error, record it; do not bypass browser certificate or security-policy warnings.

The workflow is deliberately manual. This PR does **not** enable Pages settings,
run a production deployment, or claim that the example URL is already live.
The build job only creates/uploads static files. Pages deployment permissions
are confined to the manual deployment job. No unauthenticated development,
broker, Python API, Chii, or remote evaluation endpoint is published.

The artifact contains nine HTML/CSS/JS/JSON assets, a SHA-256 build manifest,
and `.nojekyll`. There are no server programs or credentials in that directory.
The manifest identifies the checkout and whether it was dirty; hashes detect
asset changes, not publisher authenticity. This demo does not send telemetry.

## Build once and use any HTTPS static host

Node 20+ is sufficient for the demo build; Python is not needed to display or
exercise the page console.

```sh
npm ci
npm run build:demo
```

Upload **only the contents of `dist/iphone-demo/`** to your HTTPS static host.
Relative asset URLs support hosting under a subdirectory such as `/Elyon/`.
Use the host's actual HTTPS URL on the phone. You can also download the Pages
build artifact from its Actions run and deploy those files elsewhere.

For a desktop-only local preview:

```sh
npm run preview:demo
# http://127.0.0.1:4173
```

The preview server binds to loopback; that localhost URL is not reachable from
your iPhone. Do not expose it or the Python/Chii services through a public tunnel.
Use static HTTPS hosting for the phone.

## What to exercise on the phone

1. Tap **Open console**, then minimize it. Drag the square launcher. Reopen it;
   drag the ELYON handle and resize with ↕. Rotate the phone and ensure the handles
   remain reachable.
2. In Console's **JS** mode, run `document.title` and `Promise.resolve(42)`.
   Use **Await** mode for `await Promise.resolve(42)`. Trigger an error with
   `throw new Error('manual device test')` in JS mode. Errors should be readable;
   page policy can block evaluation and must be reported instead of bypassed.
3. Focus the expression field with the iOS keyboard open. Check the Run button,
   typing, tab navigation, orientation changes, and returning after dismissal.
4. Minimize the console. Tap **Fetch JSON**, **XHR JSON**, and **Abort XHR**.
   Reopen Network. Compare the displayed phases/status to the device lab's actual
   XHR event output. A response with status 0 is not automatically a network failure:
   opaque Fetch responses can fulfill with that status.
5. In Elements, inspect `#inspect-target`. Check the rectangle, computed metadata,
   and highlight. Choose **Pick** and tap an element. Escape or the launcher cancels
   picking. It inspects this document, not arbitrary apps, cross-origin frames, or
   closed shadow roots.
6. Tap **Write demo storage**, then view/edit/delete that one key in Storage.
   Denied storage or quota errors should appear explicitly. Storage is scoped to
   the origin, not the repository path; use a dedicated test origin for sensitive
   work. Preferences and all 20 themes should survive reloading when storage permits.
7. Export a redacted session. Confirm it contains source/coverage labels and no
   console message or URL values. DOM/storage values are not part of that export.
8. **Remove console**, then reinstall it. A page action should produce one record,
   not duplicate records. Removing the console discards its volatile session rows.

Do not run an infinite loop to test independence here: the page console shares
this document's thread. Use the independent desktop broker harness for stall/crash
preservation tests. There is no native Gecko or privileged Safari bridge in this build.

## Install on a page you control

Copy these five files together to a path your page permits:
`mobile-console.js`, `mobile-console.css`, `network.js`, `page-runtime.js`, `themes.js`.

```html
<script type="module">
  import { createConsole } from "/devtools/mobile-console.js";
  createConsole().open();
</script>
```

Module/style loading and evaluation remain subject to your page's CSP, module CORS,
and Trusted Types rules. Elyon does not bypass them. Prefer same-origin assets.
If the module is blocked entirely it cannot report capabilities itself; the device
lab's startup message remains visible. A stylesheet failure is also exposed through
`api.snapshot().capabilities.styles` if the UI cannot render correctly.

`createConsole()` is idempotent; keep the returned API. Use `api.destroy()` for
teardown, and call `createConsole()` again to reinstall. `api.snapshot()` is redacted
by default; `{redacted:false}` is explicit local access to potentially sensitive data.
These page-session snapshots are **not broker evidence archives**.

## Report a device result

Record: build manifest/commit, phone model, actual iOS version, Safari/Reynard
version and installation channel, portrait/landscape, keyboard language, steps,
expected/observed behavior, capability states, and a redacted export. Do not include
credentials, pairing files, raw storage values, or private URLs. Physical iPhone
and native-engine validation remain outstanding until such a run is actually made.
