# elyon-observer/0.1

This is an Elyon adapter contract. It defines no Gecko RDP actor or command.
The implemented producer is desktop Chromium through public Playwright 1.62.0 APIs;
the synthetic producer exists for regression fixtures. `native-gecko` attachments
are rejected until an actual adapter has been validated.

The broker runs in a different OS process from inspected content. POST JSON to its
loopback `/command` using the token from the mode-0600 endpoint file. Origin-bearing
requests are denied. There is no browser-to-broker CORS API. Use the CLI or local
Python client. Commands have `protocol: "elyon-observer/0.1"` and `type`. Unknown
fields fail validation. See `elyon/protocol.py:MESSAGES` for executable field schemas.

| Message | Fields in addition to protocol/type | Result |
|---|---|---|
| hello | none | capabilities/limits/unavailable points |
| attach | scope object, source, capabilities | fresh attachment identity, credit |
| target.upsert | attachment, target, parent (identity or null), targetKind | persisted registry transition |
| target.end | attachment, target, reason | ends generation, invalidates active readiness |
| start | attachment, capture, revision, plan object, target | requested, **not activated** |
| activation | attachment, capture, revision, target | collector acknowledgment, active |
| events | attachment, batch | durable ack IDs, duplicates, renewed credit |
| gap | attachment, reason, missing (decimal-string range or null) | incomplete coverage |
| health | attachment, healthy boolean, reason | independent health update |
| handle | attachment, id (evidence ID) | bounded local metadata handle |
| read | attachment, handle, fields | local fields; unsupported fields explicitly unavailable |
| release | attachment, handles | idempotent release |
| stop | attachment, capture | stop-requested immediately |
| stopped | attachment, capture | separate producer stopped acknowledgment |
| detach | attachment | invalidates attachment, releases handles and producer/target state |
| snapshot | none | detached immutable copy of evidence graph and coverage |
| export | optional redacted boolean (default true) | portable archive |

One attachment and one active capture at a time. Scope is descriptive for this
trusted local research producer, not an access-control boundary for untrusted
extensions. The broker authenticates the client but cannot prove a producer's
truthfulness. It validates shape, identity, sequencing and existing evidence refs.

Capabilities have separate boolean `supported`, `permitted`, `enabled`, `healthy`
states. `requests` must have all four true for activation; unsupported native
capabilities are false. A collector start request cannot substitute for activation.
Navigation generation changes invalidate readiness; stale acknowledgments fail.
Completed captures do not change coverage when later navigation occurs.

## Evidence envelope

Each event requires exactly: `protocol`, `attachment`, `capture`, `revision`,
`producer`, `epoch`, `sequence`, `id`, `target`, `timestamp`, `clock`, `kind`,
`point`, `evidence`, `certainty`, `source`.

Sequence and target generation are canonical unsigned 64-bit **decimal strings**.
The broker compares them as Python integers; JSON never converts them to floating
point. Sequence starts at 1 per producer/epoch within an attachment and continues
across captures. Duplicate retransmission must preserve the exact original envelope,
including timestamp. Gaps are recorded; late/out-of-order conflicting events fail.
Whole batches validate before append. Acks follow file fsync. Event IDs generated
by the host are SHA-256 of attachment, producer, epoch and decimal sequence, not of
webpage message payloads. The hash establishes an ID, not source authenticity.

Targets are `{id, generation}` or null when unknown. `timestamp` is finite and
`clock` names its origin; timestamps across clocks do not establish causality.
The current desktop host uses a coordinated page/navigation generation, not a
native Gecko inner-window ID. Frame, worker and navigation requests whose document
identity it cannot establish have null targets.

Families: LoadIntent, RequestAttempt, ResponseVersion, Redirect, CacheObservation,
ServiceWorkerHandling, PolicyDecision, Exposure, Termination, Coverage, Gap,
Relationship. Certainty is observed, derived, inferred, unavailable or redacted.
Payloads are evidence objects; optional fields stay missing/null, never filled by
resource-category heuristics. Mixed-certainty subclaims must carry their own
certainty (as the desktop source-classification/exposure fields do).

Relationships carry `from`, `to`, `relation` and supporting evidence IDs (`support`),
or an explicitly named `rule` for inferred relationships. Endpoints/support must
already exist or appear earlier in the same batch. No URL/time/category joins.
The Chromium host derives redirects from `Request.redirected_from` object identity,
not from status 302 alone. It links `Response.request` to its RequestAttempt.
`Response.status` is Playwright response metadata, **not proof of raw wire status**
(notably revalidation), and never a claim about Fetch/XHR page exposure.

## Resource and persistence contract

* At most 64 events/batch, 16 KiB/event and 256 KiB/command. Credit is a synchronous
  bounded send window replenished by durable ack, not an unlimited streaming queue.
  Sender must retain unacked data and stop when credit is zero. The desktop host
  sends one event per transaction and fails closed on ingestion errors.
* One append-only journal, hard maximum 16 MiB including control records; 64 KiB
  reserved from evidence ingestion for final coverage/control. No evidence eviction.
  Journal-full persists a gap and grants zero credit. Once all space is exhausted,
  additional controls fail explicitly; snapshot/export remain available. Metadata
  floods can also exhaust capacity; no bounded system promises infinite control history.
* Exclusive writer lock, fsync-before-ack, immutable copies returned to callers.
  Interrupted/truncated writes are diagnosed and the file preserved for recovery;
  this milestone does not silently repair or truncate journals. Restart recovers
  delivered evidence but does not assert a live adapter connection.
* 256 captures/journal, 256 targets/attachment, 128 producer/epochs/attachment; metadata
  history is itself limited by the journal. Start a fresh journal when exhausted.
* 128 handles, 16 KiB each, 30-second monotonic expiry. Reads never call inspected
  content. Release, detach and shutdown clear them; handles do not survive restart.
* Desktop request-object retention is bounded at 256; overflow produces a gap.
  Playwright's own internal queues are upstream, not an engine-level backpressure
  guarantee. No native collector retention or hardware overhead claim is made.

Exports contain manifest, protocol/version, configuration and target transitions,
evidence, missing data, gaps and permitted artifact list (currently empty). SHA-256
detects archive alteration but is not a signature. Import validates the digest and
replays the command contract into staging before exclusively creating a new journal.
Redacted export removes all free-form nonrelationship evidence and scope/plan data,
preserving explicit redaction markers and structural graph IDs. IDs, target names,
producer names, observation labels, inference rule names and relationship labels
are retained: producers must keep secrets out of these structural fields. Raw local
journals and snapshots remain sensitive. There are no retained body artifacts.
