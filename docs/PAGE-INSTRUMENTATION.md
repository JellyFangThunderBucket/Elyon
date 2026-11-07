# Page instrumentation contract

The existing independent Python broker/protocol is unchanged. The page console
has a separate volatile snapshot format (`elyon-page-console`, version 2) and
explicitly sets `independentEvidence:false`. Current enabled flags and an incomplete,
current-document coverage declaration are included; settings-change history is not
retained. Local record IDs are scoped to one console instance, not cross-session IDs. A cooperative page can alter any
page-level observer; these are not signed or privileged browser observations.

## Fetch

Arguments and receiver are forwarded exactly once. Data-descriptor/native Request
metadata is read without invoking user URL coercion or RequestInit getters again.
Unknown metadata remains null. Responses and rejection objects pass through unchanged;
no response body, clone, headers, or body reader is consumed by the recorder.

When enabled, the observer returns a chained Promise. This changes Promise identity
and microtask timing; it retains rejection propagation rather than silently marking
the returned request handled. When disabled, the original return value is passed
through. Non-Promise third-party return values are passed through with an explicit
observation gap. No timing-equivalence claim is made. Reflection can still trigger
Proxy traps; arbitrary hostile page objects cannot be made transparent to inspection.

A fulfilled Fetch means response metadata became available, not that the response
body was consumed or that HTTP status indicates success. Opaque status 0 and HTTP
error statuses are preserved. Rejections do not establish a native policy decision.

## XHR

Only successful opens replace the previous generation's metadata. Invalid open/send
calls retain native exceptions and do not overwrite an already active request.
Observers use the XHR object's native readyState/status/responseURL getters. Request
identity comes from the particular open/send lifecycle, never URL/time matching.

The recorder listens for readystatechange, load, error, timeout, abort, and loadend.
It snapshots available metadata at DONE rather than reading a potentially reused
object only at loadend. It does not dispatch, cancel, or reorder browser XHR events.
A reentrant open releases the previous observer and records
`reopened-before-loadend`. A prior terminal event is not attributed to a new pending
request. Existing page handlers can run before an observer: if they reopen before
it can see a completion phase, that phase stays missing. A prior observed status
may be retained, but the UI must not invent completion information.

Rows contain a locally ordered phase trace. `request-start`, `done`, `unavailable`,
and `observation-ended` describe observer lifecycle transitions; named XHR events
are actual listener observations. The trace is bounded at 32 entries and reports
truncation. User event ordering is compared with an uninstrumented control in tests.
Synchronous requests and nested reuse are regression fixtures, not recommendations
for application code.

## Lifecycle and limits

Installation is idempotent across repeated calls/module URL variants via a page
registry. Protected/missing APIs are reported as denied/unsupported. Teardown restores
owned slots only; it does not overwrite a wrapper installed later by the page.
If the page freezes a slot after installation, restoration can be prevented; the
remaining wrapper is dormant and forwarding. Protected globals can also prevent
publishing the convenience alias; retain the API returned by createConsole().

Pending XHR listeners and window/document/viewport listeners are removed, animation
frames/timers/highlights are cancelled, and object URLs are revoked. Promise observers
and user evaluations already awaiting settlement cannot be forcibly cancelled; they
become inactive and do not write new UI records after teardown.

Retention is 100/500/1000/2000 rows by preference; only the last 250 matching rows
render. Older-row eviction counters and the volatile policy are included in snapshots.
Only the active panel is rendered; a minimized console does not repaint hidden lists.
At most 128 active XHR observers and 128 unsettled Fetch observers are admitted;
further calls still execute but get an explicit observer-capacity gap.

Object previews are depth/property/length bounded. Ordinary property getters and
custom toString methods are not invoked. Native Error/DOMException metadata is
formatted separately; Proxy reflection failures are shown. The REPL supports global
script evaluation and explicit async-expression mode. It cannot interrupt a loop
or cancel asynchronous work started by evaluated application code.

## Redaction

Redacted snapshots/exports remove messages, URL/responseURL values, and arbitrary
method strings. Only standard HTTP method names are retained. DOM and storage
contents are excluded. The remaining source, capability, outcome, gap, and retention
fields are machine-generated; phase traces retain numeric state/status/timing.
Raw snapshots are explicit local access. Deep copies prevent callers from mutating
retained rows through a returned snapshot. None of this turns page data into
independent broker evidence or guarantees truthfulness against a hostile page.
